import json
import hashlib
import html
import re
from datetime import datetime, timedelta

from Scripts.ai_provider import OpenAIProvider, configured_model
from Scripts.skill_taxonomy import (
    get_allowed_skill_baskets_text,
    clean_skill_basket,
    normalize_certification,
    clean_requirement_level,
    clean_text_value,
)
from Scripts.prompt_loader import build_extraction_prompt
from App.app_utils.database import (
    get_cached_extraction,
    save_cached_extraction,
    record_status_change,
    record_follow_up_event,
    get_connection,
)

ALLOWED_BASKET_NAMES = set(
    get_allowed_skill_baskets_text().replace("- ", "").split("\n")
)

# ---------------------------------------------------------------------
# 1. OpenAI Helper
# ---------------------------------------------------------------------

def ask_openai(prompt: str, provider: OpenAIProvider | None = None) -> dict:
    """
    Sends a prompt to OpenAI and returns the structured extraction.
    """
    return (provider or OpenAIProvider()).extract_job_data(prompt)


# ---------------------------------------------------------------------
# 2. JD Pre-Cleaning
# ---------------------------------------------------------------------

def normalize_job_description_text(job_description: str) -> str:
    """Normalize pasted HTML/Markdown artifacts without changing the source record."""

    text = html.unescape(str(job_description or ""))
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = re.sub(r"\\\s*\n", "\n", text)
    text = re.sub(r"\*{1,3}", "", text)

    normalized_lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            normalized_lines.append(line)

    return "\n".join(normalized_lines).strip()


def clean_job_description_for_ai(job_description: str, max_chars: int = 6000) -> str:
    """
    Preserve the posting's substantive text for extraction.

    Section headings such as "About Us" can occur before the role details, so
    truncating at a heading can discard the entire job description.
    """

    if not job_description:
        return ""

    return normalize_job_description_text(job_description)[:max_chars]


# ---------------------------------------------------------------------
# 3. JSON Cleaning Helper
# ---------------------------------------------------------------------

def extract_json_from_ai_response(response_text: str) -> dict:
    """
    Extracts JSON safely from an AI response.

    Older model responses may sometimes wrap JSON in markdown fences or add small explanations.
    This function tries to recover the JSON object.
    """
    if not response_text:
        return {}

    cleaned = response_text.strip()
    cleaned = cleaned.replace("```json", "")
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return {}

    return {}


# ---------------------------------------------------------------------
# 4. Lightweight Prompt Builder
# ---------------------------------------------------------------------

def build_prompt(job_description: str) -> str:
    """
    Builds a lightweight JD extraction prompt.

    Structured skills and certifications are handled mostly by Python fallback.
    The LLM only extracts general metadata and simple lists.
    """

    return build_extraction_prompt(job_description)


# ---------------------------------------------------------------------
# 5. General Cleaning Helpers
# ---------------------------------------------------------------------

def clean_list(value) -> list:
    """
    Converts AI list fields into clean Python lists.
    """
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str) and value.strip():
        return [value.strip()]

    return []


def keyword_found(keyword: str, text: str) -> bool:
    """
    Safer keyword matching using alphanumeric boundaries.

    This avoids false matches like:
    - 'lan' inside 'analyst'
    - 'wan' inside unrelated words

    It also supports certification names with symbols:
    - A+
    - Network+
    - Security+
    """
    pattern = rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])"
    return re.search(pattern, text) is not None

# ---------------------------------------------------------------------
# 6. Structured Output Cleaning
# ---------------------------------------------------------------------

def clean_structured_skills(raw_skills) -> list:
    """
    Cleans and validates structured skills returned by the AI.
    """
    cleaned_skills = []
    seen_skills = set()

    if not isinstance(raw_skills, list):
        return cleaned_skills

    for skill in raw_skills:
        if not isinstance(skill, dict):
            continue

        raw_skill = clean_text_value(skill.get("raw_skill"))
        specific_skill = clean_text_value(skill.get("specific_skill"))
        skill_basket = clean_skill_basket(skill.get("skill_basket"))

        if not raw_skill and not specific_skill:
            continue

        if not specific_skill:
            specific_skill = raw_skill

        dedupe_key = (
            specific_skill.lower(),
            skill_basket.lower(),
        )

        if dedupe_key in seen_skills:
            continue

        seen_skills.add(dedupe_key)

        cleaned_skills.append(
            {
                "raw_skill": raw_skill,
                "specific_skill": specific_skill,
                "skill_basket": skill_basket,
            }
        )

    return cleaned_skills


def clean_structured_certifications(raw_certifications) -> list:
    """
    Cleans and validates structured certifications returned by the AI.
    """
    cleaned_certifications = []
    seen_certifications = set()

    if not isinstance(raw_certifications, list):
        return cleaned_certifications

    for cert in raw_certifications:
        if not isinstance(cert, dict):
            continue

        raw_certification = clean_text_value(cert.get("raw_certification"))
        certification_name = clean_text_value(cert.get("certification_name"))
        certification_short_name = clean_text_value(cert.get("certification_short_name"))
        requirement_level = clean_requirement_level(cert.get("requirement_level"))

        if not raw_certification and not certification_name and not certification_short_name:
            continue

        cert_source = raw_certification or certification_short_name or certification_name
        normalized_cert = normalize_certification(cert_source)

        if not certification_name:
            certification_name = normalized_cert["certification_name"]

        if not certification_short_name:
            certification_short_name = normalized_cert["certification_short_name"]

        related_baskets = cert.get("related_baskets")

        if not isinstance(related_baskets, list) or not related_baskets:
            related_baskets = normalized_cert["related_baskets"]

        cleaned_related_baskets = []

        for basket in related_baskets:
            cleaned_basket = clean_skill_basket(basket)

            if cleaned_basket not in cleaned_related_baskets:
                cleaned_related_baskets.append(cleaned_basket)

        if not cleaned_related_baskets:
            cleaned_related_baskets = ["Other"]

        dedupe_key = (
            certification_short_name.lower(),
            certification_name.lower(),
            tuple(sorted(cleaned_related_baskets)),
        )

        if dedupe_key in seen_certifications:
            continue

        seen_certifications.add(dedupe_key)

        cleaned_certifications.append(
            {
                "raw_certification": raw_certification,
                "certification_name": certification_name,
                "certification_short_name": certification_short_name,
                "related_baskets": cleaned_related_baskets,
                "requirement_level": requirement_level,
            }
        )

    return cleaned_certifications


# ---------------------------------------------------------------------
# 7. Deterministic Skill and Certification Extraction
# ---------------------------------------------------------------------

def build_keyword_fallback_structured_data(job_description: str) -> dict:
    """
    Deterministic fallback extraction for common IT skills and certifications.

    This ensures long JDs still produce useful structured skills even if
    the local LLM fails, times out, or returns weak JSON.
    """
    text = job_description.lower() if job_description else ""

    skill_rules = [
        # Microsoft 365
        ("microsoft 365", "Microsoft 365", "Microsoft 365 Administration"),
        ("office 365", "Office 365", "Microsoft 365 Administration"),
        ("m365", "Microsoft 365", "Microsoft 365 Administration"),
        ("outlook", "Microsoft Outlook", "Microsoft 365 Administration"),
        ("microsoft teams", "Microsoft Teams", "Microsoft 365 Administration"),
        ("sharepoint", "SharePoint Online", "Microsoft 365 Administration"),
        ("onedrive", "OneDrive for Business", "Microsoft 365 Administration"),
        ("exchange online", "Exchange Online", "Microsoft 365 Administration"),
        ("microsoft exchange", "Exchange Online", "Microsoft 365 Administration"),

        # Identity
        ("entra id", "Microsoft Entra ID", "Microsoft Entra ID & Identity"),
        ("azure ad", "Azure AD", "Microsoft Entra ID & Identity"),
        ("mfa", "Multi-Factor Authentication", "Microsoft Entra ID & Identity"),
        ("multi-factor authentication", "Multi-Factor Authentication", "Microsoft Entra ID & Identity"),
        ("conditional access", "Conditional Access", "Microsoft Entra ID & Identity"),
        ("sign-in", "Sign-in Troubleshooting", "Microsoft Entra ID & Identity"),

        # Active Directory
        ("active directory", "Active Directory", "Active Directory"),
        ("password reset", "Password Reset", "Active Directory"),
        ("password resets", "Password Reset", "Active Directory"),
        ("group policy", "Group Policy", "Active Directory"),
        ("gpo", "Group Policy", "Active Directory"),
        ("onboarding", "User Onboarding", "Active Directory"),
        ("offboarding", "User Offboarding", "Active Directory"),

        # Intune / Endpoint
        ("intune", "Microsoft Intune", "Microsoft Intune & Endpoint Management"),
        ("autopilot", "Windows Autopilot", "Microsoft Intune & Endpoint Management"),
        ("mdm", "Mobile Device Management", "Microsoft Intune & Endpoint Management"),
        ("device compliance", "Device Compliance", "Microsoft Intune & Endpoint Management"),

        # Windows endpoint
        ("windows 10", "Windows 10 Support", "Windows Endpoint Support"),
        ("windows 11", "Windows 11 Support", "Windows Endpoint Support"),
        ("imaging", "Device Imaging", "Windows Endpoint Support"),
        ("soe", "Standard Operating Environment", "Windows Endpoint Support"),

        # Hardware / Field
        ("laptop", "Laptop Support", "Hardware & Field Support"),
        ("laptops", "Laptop Support", "Hardware & Field Support"),
        ("desktop", "Desktop Support", "Hardware & Field Support"),
        ("desktops", "Desktop Support", "Hardware & Field Support"),
        ("printer", "Printer Support", "Hardware & Field Support"),
        ("printers", "Printer Support", "Hardware & Field Support"),
        ("mobile device", "Mobile Device Support", "Hardware & Field Support"),
        ("mobile devices", "Mobile Device Support", "Hardware & Field Support"),
        ("meeting room", "Meeting Room Technology", "Hardware & Field Support"),
        ("onsite", "Onsite Support", "Hardware & Field Support"),
        ("remote support", "Remote Support", "Hardware & Field Support"),

        # Service Desk / ITSM
        ("ticket", "Ticketing", "Service Desk & ITSM"),
        ("ticketing", "Ticketing", "Service Desk & ITSM"),
        ("jira", "Jira Service Management", "Service Desk & ITSM"),
        ("servicenow", "ServiceNow", "Service Desk & ITSM"),
        ("incident", "Incident Management", "Service Desk & ITSM"),
        ("incidents", "Incident Management", "Service Desk & ITSM"),
        ("request", "Service Request Management", "Service Desk & ITSM"),
        ("requests", "Service Request Management", "Service Desk & ITSM"),
        ("sla", "SLA Management", "Service Desk & ITSM"),
        ("escalation", "Escalation Management", "Service Desk & ITSM"),

        # Documentation
        ("knowledge base", "Knowledge Base Documentation", "Documentation & Communication"),
        ("documentation", "Documentation", "Documentation & Communication"),
        ("documenting", "Documentation", "Documentation & Communication"),
        ("runbook", "Runbook Documentation", "Documentation & Communication"),
        ("handover", "Handover Notes", "Documentation & Communication"),
        ("customer service", "Customer Service", "Documentation & Communication"),
        ("stakeholder", "Stakeholder Communication", "Documentation & Communication"),

        # Network fundamentals
        ("tcp/ip", "TCP/IP", "General Network Fundamentals"),
        ("ip protocols", "IP Protocols", "General Network Fundamentals"),
        ("ip networks", "IP Networks", "General Network Fundamentals"),
        ("ip address", "IP Address Management", "General Network Fundamentals"),
        ("ip addresses", "IP Address Management", "General Network Fundamentals"),
        ("dns", "DNS", "General Network Fundamentals"),
        ("dhcp", "DHCP", "General Network Fundamentals"),
        ("vpn", "VPN", "General Network Fundamentals"),
        ("subnet", "Subnetting", "General Network Fundamentals"),
        ("subnetting", "Subnetting", "General Network Fundamentals"),
        ("ip addressing", "IP Addressing", "General Network Fundamentals"),
        ("lan", "LAN/WAN Networking", "General Network Fundamentals"),
        ("wan", "LAN/WAN Networking", "General Network Fundamentals"),
        ("ping", "Ping", "General Network Fundamentals"),
        ("traceroute", "Traceroute", "General Network Fundamentals"),

        # Cisco Routing / Switching
        ("cisco", "Cisco Networking", "Cisco Routing & Switching"),
        ("router", "Router Configuration", "Cisco Routing & Switching"),
        ("routers", "Router Configuration", "Cisco Routing & Switching"),
        ("switch", "Switch Configuration", "Cisco Routing & Switching"),
        ("switches", "Switch Configuration", "Cisco Routing & Switching"),
        ("vlan", "VLANs", "Cisco Routing & Switching"),
        ("vlans", "VLANs", "Cisco Routing & Switching"),
        ("ospf", "OSPF", "Cisco Routing & Switching"),
        ("bgp", "BGP", "Cisco Routing & Switching"),
        ("is-is", "IS-IS", "General Network Fundamentals"),
        ("cisco ios-xr", "Cisco IOS-XR", "Cisco Routing & Switching"),
        ("cisco nexus", "Cisco Nexus", "Cisco Routing & Switching"),
        ("arista", "Arista Networking", "General Network Fundamentals"),
        ("eigrp", "EIGRP", "Cisco Routing & Switching"),
        ("stp", "Spanning Tree Protocol", "Cisco Routing & Switching"),
        ("routing", "Routing", "Cisco Routing & Switching"),
        ("switching", "Switching", "Cisco Routing & Switching"),

        # Wireless
        ("wi-fi", "Wi-Fi Troubleshooting", "Wireless / WLAN"),
        ("wifi", "Wi-Fi Troubleshooting", "Wireless / WLAN"),
        ("wlan", "WLAN", "Wireless / WLAN"),
        ("access point", "Access Points", "Wireless / WLAN"),
        ("access points", "Access Points", "Wireless / WLAN"),
        ("ssid", "SSID", "Wireless / WLAN"),
        ("802.11", "802.11 Wireless", "Wireless / WLAN"),

        # SD-WAN / Enterprise WAN
        ("sd-wan", "SD-WAN", "SD-WAN & Enterprise WAN"),
        ("viptela", "Cisco Viptela SD-WAN", "SD-WAN & Enterprise WAN"),
        ("meraki", "Cisco Meraki", "SD-WAN & Enterprise WAN"),
        ("velocloud", "VMware Velocloud SD-WAN", "SD-WAN & Enterprise WAN"),
        ("mpls", "MPLS", "SD-WAN & Enterprise WAN"),
        ("vrf", "VRF", "SD-WAN & Enterprise WAN"),
        ("qos", "Quality of Service", "SD-WAN & Enterprise WAN"),
        ("evpn-vxlan", "EVPN-VXLAN", "SD-WAN & Enterprise WAN"),
        ("vxlan", "VXLAN", "SD-WAN & Enterprise WAN"),
        ("evpn", "EVPN", "SD-WAN & Enterprise WAN"),
        ("aci", "Cisco ACI", "SD-WAN & Enterprise WAN"),
        ("mobile core", "Mobile Core Network", "SD-WAN & Enterprise WAN"),
        ("data center fabric", "Data Center Fabric", "SD-WAN & Enterprise WAN"),

        # Voice / VoIP
        ("sip", "SIP", "Voice / VoIP Networking"),
        ("voip", "VoIP", "Voice / VoIP Networking"),
        ("sip traces", "SIP Trace Analysis", "Voice / VoIP Networking"),
        ("teams phone", "Microsoft Teams Phone", "Voice / VoIP Networking"),
        ("broadworks", "Cisco BroadWorks", "Voice / VoIP Networking"),
        ("ivr", "IVR", "Voice / VoIP Networking"),
        ("telecom", "Telecommunications Networking", "General Network Fundamentals"),

        # Firewall / Security appliances
        ("firewall", "Firewall Concepts", "Firewall & Network Security"),
        ("firewalls", "Firewall Concepts", "Firewall & Network Security"),
        ("palo alto", "Palo Alto Firewall", "Firewall & Network Security"),
        ("fortigate", "FortiGate", "Firewall & Network Security"),
        ("fortinet", "Fortinet Firewall", "Firewall & Network Security"),
        ("checkpoint", "Check Point Firewall", "Firewall & Network Security"),
        ("check point", "Check Point Firewall", "Firewall & Network Security"),
        ("f5", "F5 Load Balancer / Security Appliance", "Firewall & Network Security"),
        ("ids", "Intrusion Detection Systems", "Firewall & Network Security"),
        ("nac", "Network Access Control", "Firewall & Network Security"),
        ("security policies", "Security Policy Management", "Firewall & Network Security"),
        ("network access control", "Network Access Control", "Firewall & Network Security"),

        # Cybersecurity fundamentals
        ("phishing", "Phishing Awareness", "Cybersecurity Fundamentals"),
        ("suspicious activity", "Suspicious Activity Escalation", "Cybersecurity Fundamentals"),
        ("vulnerability", "Vulnerability Awareness", "Cybersecurity Fundamentals"),
        ("unauthorized access", "Unauthorized Access Prevention", "Cybersecurity Fundamentals"),
        ("security principles", "Network Security Principles", "Cybersecurity Fundamentals"),

        # Azure
        ("azure", "Microsoft Azure", "Azure Cloud"),
        ("storage account", "Azure Storage Accounts", "Azure Cloud"),
        ("storage accounts", "Azure Storage Accounts", "Azure Cloud"),

        # Linux / Server
        ("linux", "Linux Server Support", "Linux & Server Support"),
        ("bash", "Bash Scripting", "Linux & Server Support"),
        ("server maintenance", "Server Maintenance", "Linux & Server Support"),
        ("patching", "Patching / Maintenance", "Cybersecurity Fundamentals"),

        # Virtualization
        ("vmware", "VMware", "Virtualization"),
        ("virtual machine", "Virtual Machines", "Virtualization"),
        ("virtual machines", "Virtual Machines", "Virtualization"),

        # Backup / Storage
        ("backup", "Backup", "Backup & Storage"),
        ("backups", "Backup", "Backup & Storage"),
        ("disaster recovery", "Disaster Recovery", "Backup & Storage"),

        # App / SaaS
        ("salesforce", "Salesforce Support", "Application / SaaS Support"),
        ("saas", "SaaS Support", "Application / SaaS Support"),
        ("sql", "SQL Basics", "Application / SaaS Support"),

        # Scripting / Automation
        ("python", "Python", "Scripting & Automation"),
        ("netmiko", "Netmiko", "Scripting & Automation"),
        ("nornir", "Nornir", "Scripting & Automation"),
        ("napalm", "NAPALM", "Scripting & Automation"),
        ("netbox", "NetBox", "General Network Fundamentals"),
        ("ci/cd", "CI/CD", "Scripting & Automation"),
        ("powershell", "PowerShell", "Scripting & Automation"),
        ("automation", "Automation", "Scripting & Automation"),

        # AI / Productivity
        ("ai tools", "AI Tools", "AI & Digital Productivity"),
        ("responsible ai", "Responsible AI Use", "AI & Digital Productivity"),
        ("generative ai", "Generative AI Awareness", "AI & Digital Productivity"),
    ]

    certification_rules = [
        # ITSM
        ("itil foundation", "ITIL Foundation", "ITIL", [
            "Service Desk & ITSM",
        ]),
        ("itil", "ITIL Foundation", "ITIL", [
            "Service Desk & ITSM",
        ]),

        # Cisco
        ("ccna", "Cisco Certified Network Associate", "CCNA", [
            "General Network Fundamentals",
            "Cisco Routing & Switching",
            "Wireless / WLAN",
        ]),
        ("cisco certified network associate", "Cisco Certified Network Associate", "CCNA", [
            "General Network Fundamentals",
            "Cisco Routing & Switching",
            "Wireless / WLAN",
        ]),

        ("ccnp", "Cisco Certified Network Professional", "CCNP", [
            "Cisco Routing & Switching",
            "SD-WAN & Enterprise WAN",
        ]),
        ("cisco certified network professional", "Cisco Certified Network Professional", "CCNP", [
            "Cisco Routing & Switching",
            "SD-WAN & Enterprise WAN",
        ]),

        ("ccie", "Cisco Certified Internetwork Expert", "CCIE", [
            "Cisco Routing & Switching",
            "SD-WAN & Enterprise WAN",
        ]),
        ("cisco certified internetwork expert", "Cisco Certified Internetwork Expert", "CCIE", [
            "Cisco Routing & Switching",
            "SD-WAN & Enterprise WAN",
        ]),

        # CompTIA
        ("comptia a+", "CompTIA A+", "A+", [
            "Windows Endpoint Support",
            "Hardware & Field Support",
            "Service Desk & ITSM",
        ]),
        ("a+", "CompTIA A+", "A+", [
            "Windows Endpoint Support",
            "Hardware & Field Support",
            "Service Desk & ITSM",
        ]),

        ("comptia network+", "CompTIA Network+", "Network+", [
            "General Network Fundamentals",
        ]),
        ("network+", "CompTIA Network+", "Network+", [
            "General Network Fundamentals",
        ]),

        ("comptia security+", "CompTIA Security+", "Security+", [
            "Cybersecurity Fundamentals",
            "Firewall & Network Security",
        ]),
        ("security+", "CompTIA Security+", "Security+", [
            "Cybersecurity Fundamentals",
            "Firewall & Network Security",
        ]),

        ("comptia linux+", "CompTIA Linux+", "Linux+", [
            "Linux & Server Support",
        ]),
        ("linux+", "CompTIA Linux+", "Linux+", [
            "Linux & Server Support",
        ]),

        # Microsoft fundamentals
        ("ms-900", "Microsoft 365 Certified: Fundamentals", "MS-900", [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ]),
        ("microsoft 365 certified: fundamentals", "Microsoft 365 Certified: Fundamentals", "MS-900", [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ]),
        ("microsoft 365 fundamentals", "Microsoft 365 Certified: Fundamentals", "MS-900", [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ]),

        ("az-900", "Microsoft Azure Fundamentals", "AZ-900", [
            "Azure Cloud",
        ]),
        ("microsoft azure fundamentals", "Microsoft Azure Fundamentals", "AZ-900", [
            "Azure Cloud",
        ]),
        ("azure fundamentals", "Microsoft Azure Fundamentals", "AZ-900", [
            "Azure Cloud",
        ]),

        ("sc-900", "Microsoft Security, Compliance, and Identity Fundamentals", "SC-900", [
            "Microsoft Entra ID & Identity",
            "Cybersecurity Fundamentals",
        ]),
        ("microsoft security, compliance, and identity fundamentals",
         "Microsoft Security, Compliance, and Identity Fundamentals", "SC-900", [
             "Microsoft Entra ID & Identity",
             "Cybersecurity Fundamentals",
         ]),

        # Microsoft associate-level
        ("az-104", "Microsoft Azure Administrator", "AZ-104", [
            "Azure Cloud",
            "Azure Networking",
            "Scripting & Automation",
        ]),
        ("microsoft azure administrator", "Microsoft Azure Administrator", "AZ-104", [
            "Azure Cloud",
            "Azure Networking",
            "Scripting & Automation",
        ]),
        ("azure administrator", "Microsoft Azure Administrator", "AZ-104", [
            "Azure Cloud",
            "Azure Networking",
            "Scripting & Automation",
        ]),

        ("az-700", "Microsoft Azure Network Engineer Associate", "AZ-700", [
            "Azure Networking",
            "General Network Fundamentals",
        ]),
        ("microsoft azure network engineer associate", "Microsoft Azure Network Engineer Associate", "AZ-700", [
            "Azure Networking",
            "General Network Fundamentals",
        ]),
        ("azure network engineer associate", "Microsoft Azure Network Engineer Associate", "AZ-700", [
            "Azure Networking",
            "General Network Fundamentals",
        ]),

        ("md-102", "Microsoft Endpoint Administrator", "MD-102", [
            "Microsoft Intune & Endpoint Management",
            "Windows Endpoint Support",
        ]),
        ("microsoft endpoint administrator", "Microsoft Endpoint Administrator", "MD-102", [
            "Microsoft Intune & Endpoint Management",
            "Windows Endpoint Support",
        ]),
        ("endpoint administrator", "Microsoft Endpoint Administrator", "MD-102", [
            "Microsoft Intune & Endpoint Management",
            "Windows Endpoint Support",
        ]),

        ("ms-102", "Microsoft 365 Administrator", "MS-102", [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ]),
        ("microsoft 365 administrator", "Microsoft 365 Administrator", "MS-102", [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ]),

        ("sc-200", "Microsoft Security Operations Analyst", "SC-200", [
            "Cybersecurity Fundamentals",
        ]),
        ("microsoft security operations analyst", "Microsoft Security Operations Analyst", "SC-200", [
            "Cybersecurity Fundamentals",
        ]),

        ("sc-300", "Microsoft Identity and Access Administrator", "SC-300", [
            "Microsoft Entra ID & Identity",
        ]),
        ("microsoft identity and access administrator", "Microsoft Identity and Access Administrator", "SC-300", [
            "Microsoft Entra ID & Identity",
        ]),

        # AWS
        ("aws certified cloud practitioner", "AWS Certified Cloud Practitioner", "AWS CCP", [
            "Azure Cloud",
        ]),
        ("aws cloud practitioner", "AWS Certified Cloud Practitioner", "AWS CCP", [
            "Azure Cloud",
        ]),

        ("aws certified solutions architect", "AWS Certified Solutions Architect", "AWS SAA", [
            "Azure Cloud",
            "General Network Fundamentals",
        ]),
        ("aws solutions architect", "AWS Certified Solutions Architect", "AWS SAA", [
            "Azure Cloud",
            "General Network Fundamentals",
        ]),

        # VMware
        ("vmware certified professional", "VMware Certified Professional", "VCP", [
            "Virtualization",
        ]),
        ("vcp", "VMware Certified Professional", "VCP", [
            "Virtualization",
        ]),

        # Linux / Red Hat
        ("rhcsa", "Red Hat Certified System Administrator", "RHCSA", [
            "Linux & Server Support",
        ]),
        ("red hat certified system administrator", "Red Hat Certified System Administrator", "RHCSA", [
            "Linux & Server Support",
        ]),

        # Security
        ("cissp", "Certified Information Systems Security Professional", "CISSP", [
            "Cybersecurity Fundamentals",
            "Firewall & Network Security",
        ]),
        ("ceh", "Certified Ethical Hacker", "CEH", [
            "Cybersecurity Fundamentals",
        ]),

        # Firewall vendors
        ("fortinet nse", "Fortinet NSE Certification", "Fortinet NSE", [
            "Firewall & Network Security",
        ]),
        ("fortinet certified professional", "Fortinet Certified Professional", "FCP", [
            "Firewall & Network Security",
        ]),
        ("fcp network security", "Fortinet Certified Professional", "FCP", [
            "Firewall & Network Security",
        ]),

        ("palo alto networks certified network security administrator",
         "Palo Alto Networks Certified Network Security Administrator", "PCNSA", [
             "Firewall & Network Security",
         ]),
        ("pcnsa", "Palo Alto Networks Certified Network Security Administrator", "PCNSA", [
            "Firewall & Network Security",
        ]),

        ("palo alto networks certified network security engineer",
         "Palo Alto Networks Certified Network Security Engineer", "PCNSE", [
             "Firewall & Network Security",
         ]),
        ("pcnse", "Palo Alto Networks Certified Network Security Engineer", "PCNSE", [
            "Firewall & Network Security",
        ]),
    ]



    structured_skills = []
    seen_skills = set()

    for keyword, specific_skill, basket in skill_rules:
        if keyword_found(keyword, text):
            key = (specific_skill.lower(), basket.lower())

            if key in seen_skills:
                continue

            seen_skills.add(key)

            structured_skills.append(
                {
                    "raw_skill": keyword,
                    "specific_skill": specific_skill,
                    "skill_basket": basket,
                }
            )

    structured_certifications = []
    seen_certs = set()

    for keyword, cert_name, short_name, baskets in certification_rules:
        if keyword_found(keyword, text):
            key = short_name.lower()

            if key in seen_certs:
                continue

            seen_certs.add(key)

            structured_certifications.append(
                {
                    "raw_certification": keyword,
                    "certification_name": cert_name,
                    "certification_short_name": short_name,
                    "related_baskets": baskets,
                    "requirement_level": "Preferred",
                }
            )

    return {
        "structured_skills": structured_skills,
        "structured_certifications": structured_certifications,
    }


# ---------------------------------------------------------------------
# 8. Domain / Title Fallback Helpers
# ---------------------------------------------------------------------

def infer_domain_from_text(job_description: str, current_domain: str = "") -> str:
    """
    Infers a domain if the LLM fails or returns Other.
    """
    if current_domain and current_domain != "Other":
        return current_domain

    text = job_description.lower() if job_description else ""

    if any(term in text for term in ["service desk", "helpdesk", "desktop support", "it support"]):
        return "IT Support"

    if any(term in text for term in ["network engineer", "ip network", "routing", "switching", "ospf", "bgp", "telecom"]):
        return "Networking"

    if any(term in text for term in ["azure", "cloud", "aws"]):
        return "Cloud"

    if any(term in text for term in ["cybersecurity", "security analyst", "siem", "soc"]):
        return "Cybersecurity"

    if any(term in text for term in ["system administrator", "systems administrator", "server"]):
        return "Systems Administration"

    if any(term in text for term in ["data centre", "data center"]):
        return "Data Centre"

    if any(term in text for term in ["infrastructure"]):
        return "Infrastructure"

    if any(term in text for term in ["telecommunications", "telecom", "mobile core"]):
        return "Telecommunications"

    return "Other"


def infer_job_title_from_text(job_description: str, current_title: str = "") -> str:
    """
    Infers or restores the advertised job title from the source text.

    The model can occasionally shorten "Junior Network Engineer" to
    "Network Engineer". Preserve a seniority or level prefix found directly
    before the model's title so the database keeps the advertised title.
    """
    text = normalize_job_description_text(job_description)

    if current_title:
        current_title = normalize_job_description_text(current_title).strip()
        # A model can import a seniority prefix from a related-job card. Keep
        # the advertised title when the source supports it, but remove an
        # unsupported prefix when the base title is present in the posting.
        if current_title.lower() not in text.lower():
            base_title = re.sub(
                r"^(?:(?:junior|senior|graduate|entry[- ]level|mid[- ]level|"
                r"associate|lead|principal|staff|chief)\s*(?:/\s*)?)+",
                "",
                current_title,
                flags=re.IGNORECASE,
            ).strip()
            if base_title and base_title != current_title and base_title.lower() in text.lower():
                return base_title
        seniority_prefixes = (
            "junior|senior|graduate|entry[- ]level|mid[- ]level|associate|"
            "lead|principal|staff|chief|assistant|deputy"
        )
        qualified_title = re.search(
            rf"\b((?:{seniority_prefixes})(?:\s*/\s*(?:{seniority_prefixes}))?\s+"
            rf"{re.escape(normalize_job_description_text(current_title).strip())})\b",
            text,
            re.IGNORECASE,
        )
        if qualified_title:
            return qualified_title.group(1).strip()

        return current_title

    title_patterns = [
        r"\b(?:as|for the role of|in the role of|position(?:ed)? as)\s+"
        r"(?:an?\s+)?([A-Za-z][A-Za-z0-9 /\-&]{2,90}?)"
        r"(?=\s*[.,;:]|\s+(?:this|the|you|we|who)\b)",
        r"Role:\s*([A-Z][A-Za-z0-9 /\-&]+)",
        r"Position:\s*([A-Z][A-Za-z0-9 /\-&]+)",
        r"Job Title:\s*([A-Z][A-Za-z0-9 /\-&]+)",
    ]

    for pattern in title_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match.group(1).strip()

    known_titles = [
        "Graduate / Junior Infrastructure Engineer",
        "Infrastructure Engineer",
        "Service Desk Analyst",
        "IT Support Officer",
        "Desktop Support Technician",
        "Network Engineer",
        "IP Network Engineer",
        "Systems Administrator",
        "Cloud Support Engineer",
    ]

    lower_text = text.lower()

    for title in known_titles:
        if title.lower() in lower_text:
            return title

    return ""


def infer_company_from_text(job_description: str, current_company: str = "") -> str:
    """
    Infers company if the LLM fails to extract it.
    """
    if current_company:
        return current_company

    text = normalize_job_description_text(job_description)

    first_lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_chunk = "\n".join(first_lines[:5]).lower()

    if "capgemini" in first_chunk:
        return "Capgemini Engineering"

    recruiter_match = re.search(
        r"\b(Leaders\s+IT)\b\s*\([^)]*\bdivision\s+of\s+Peoplebank\b",
        text,
        re.IGNORECASE,
    )
    if recruiter_match:
        return recruiter_match.group(1).strip()

    company_label = re.search(
        r"(?im)^\s*(?:company|employer|organisation|organization)\s*:\s*(.+?)\s*$",
        text,
    )
    if company_label:
        return company_label.group(1).strip()

    return ""


def infer_recruitment_entities(job_description: str, extracted_data: dict) -> dict:
    """Recover recruiter/client metadata from common consultancy wording."""

    text = normalize_job_description_text(job_description)
    entities = {
        "recruiter_name": clean_text_value(extracted_data.get("recruiter_name")),
        "parent_company": clean_text_value(extracted_data.get("parent_company")),
        "end_client_name": clean_text_value(extracted_data.get("end_client_name")),
        "end_client_industry": clean_text_value(
            extracted_data.get("end_client_industry")
        ),
        "posting_type": clean_text_value(extracted_data.get("posting_type")),
    }

    division_match = re.search(
        r"\b(?P<recruiter>Leaders\s+IT)\b\s*\([^)]*\bdivision\s+of\s+"
        r"(?P<parent>Peoplebank)\b",
        text,
        re.IGNORECASE,
    )
    if division_match:
        entities["recruiter_name"] = division_match.group("recruiter").strip()
        entities["parent_company"] = division_match.group("parent").strip()

    lower_text = text.lower()
    if not entities["posting_type"]:
        recruiter_language = (
            "recruitment" in lower_text
            or "talent consultancy" in lower_text
            or "working in partnership with" in lower_text
        )
        if entities["recruiter_name"] or recruiter_language:
            entities["posting_type"] = "Recruiter / consultancy"

    if (
        not entities["end_client_industry"]
        and entities["posting_type"] == "Recruiter / consultancy"
    ):
        if "telecommunications" in lower_text or "telecom" in lower_text:
            entities["end_client_industry"] = "Telecommunications"
        elif "banking" in lower_text or "financial services" in lower_text:
            entities["end_client_industry"] = "Banking / Financial Services"

    return entities


# ---------------------------------------------------------------------
# 9. Full AI Output Cleaning
# ---------------------------------------------------------------------

def clean_extracted_data(extracted_data: dict, job_description: str = "") -> dict:
    """
    Cleans and normalizes the full AI extraction output.
    """
    expected_schema = {
        "company": "",
        "recruiter_name": "",
        "parent_company": "",
        "end_client_name": "",
        "end_client_industry": "",
        "posting_type": "",
        "job_title": "",
        "domain": "",
        "location": "",
        "salary_range": "",
        "work_mode": "Not specified",
        "technical_skills": [],
        "soft_skills": [],
        "tools_platforms": [],
        "certifications": [],
        "domain_specific_skills": [],
        "responsibilities": [],
        "structured_skills": [],
        "structured_certifications": [],
    }

    if not isinstance(extracted_data, dict):
        extracted_data = {}

    for key, default_value in expected_schema.items():
        extracted_data.setdefault(key, default_value)

    cleaned_data = {
        "company": clean_text_value(extracted_data.get("company")),
        "recruiter_name": clean_text_value(extracted_data.get("recruiter_name")),
        "parent_company": clean_text_value(extracted_data.get("parent_company")),
        "end_client_name": clean_text_value(extracted_data.get("end_client_name")),
        "end_client_industry": clean_text_value(
            extracted_data.get("end_client_industry")
        ),
        "posting_type": clean_text_value(extracted_data.get("posting_type")),
        "job_title": clean_text_value(extracted_data.get("job_title")),
        "domain": clean_text_value(extracted_data.get("domain")),
        "location": clean_text_value(extracted_data.get("location")),
        "salary_range": clean_text_value(extracted_data.get("salary_range")),
        "work_mode": clean_text_value(extracted_data.get("work_mode")) or "Not specified",
        "technical_skills": clean_list(extracted_data.get("technical_skills")),
        "soft_skills": clean_list(extracted_data.get("soft_skills")),
        "tools_platforms": clean_list(extracted_data.get("tools_platforms")),
        "certifications": clean_list(extracted_data.get("certifications")),
        "domain_specific_skills": clean_list(extracted_data.get("domain_specific_skills")),
        "responsibilities": clean_list(extracted_data.get("responsibilities")),
        "structured_skills": clean_structured_skills(
            extracted_data.get("structured_skills")
        ),
        "structured_certifications": clean_structured_certifications(
            extracted_data.get("structured_certifications")
        ),
    }

    normalized_description = normalize_job_description_text(job_description)
    fallback_data = build_keyword_fallback_structured_data(normalized_description)

    if not cleaned_data["structured_skills"]:
        cleaned_data["structured_skills"] = fallback_data["structured_skills"]

    if not cleaned_data["structured_certifications"]:
        cleaned_data["structured_certifications"] = fallback_data["structured_certifications"]

    allowed_domains = {
        "IT Support",
        "Networking",
        "Cloud",
        "Cybersecurity",
        "Systems Administration",
        "Data Centre",
        "Infrastructure",
        "Telecommunications",
        "Other",
    }

    if cleaned_data["domain"] not in allowed_domains:
        cleaned_data["domain"] = "Other"

    cleaned_data["domain"] = infer_domain_from_text(
        normalized_description,
        cleaned_data["domain"],
    )

    cleaned_data["job_title"] = infer_job_title_from_text(
        normalized_description,
        cleaned_data["job_title"],
    )

    cleaned_data["company"] = infer_company_from_text(
        normalized_description,
        cleaned_data["company"],
    )

    cleaned_data.update(
        infer_recruitment_entities(normalized_description, cleaned_data)
    )

    if (
        cleaned_data["posting_type"] == "Direct employer"
        and not cleaned_data["recruiter_name"]
        and not cleaned_data["end_client_name"]
    ):
        cleaned_data["end_client_industry"] = ""

    if (
        cleaned_data["recruiter_name"]
        and not cleaned_data["company"]
    ):
        cleaned_data["company"] = cleaned_data["recruiter_name"]

    if (
        cleaned_data["recruiter_name"]
        and cleaned_data["parent_company"]
        and cleaned_data["company"].strip().lower()
        == cleaned_data["parent_company"].strip().lower()
    ):
        cleaned_data["company"] = cleaned_data["recruiter_name"]

    return cleaned_data


def build_extraction_warnings(extracted_data: dict, job_description: str) -> list[str]:
    """Return human-readable checks for the review screen."""

    warnings = []
    source_text = normalize_job_description_text(job_description).lower()
    title = clean_text_value(extracted_data.get("job_title"))
    company = clean_text_value(extracted_data.get("company"))

    if not title:
        warnings.append("The job title could not be detected.")
    elif title.lower() not in source_text:
        warnings.append("The extracted title was not found exactly in the source text; verify its wording.")

    if company and company.lower() not in source_text:
        warnings.append("The extracted company name was not found exactly in the source text.")

    if not extracted_data.get("technical_skills") and not extracted_data.get("tools_platforms"):
        warnings.append("No technical skills or tools were extracted; review the source description.")

    return warnings


# ---------------------------------------------------------------------
# 10. Main JD Analysis Function
# ---------------------------------------------------------------------

def analyze_jd_with_openai(job_description: str, force_refresh: bool = False) -> dict:
    """
    Analyzes a pasted job description using OpenAI structured output and
    deterministic Python cleanup.

    The cleaned JD is sent to OpenAI, while the existing taxonomy and
    deterministic validation layer keeps the stored result consistent.
    """

    if not job_description or not job_description.strip():
        return clean_extracted_data({}, job_description)

    cleaned_jd_for_ai = clean_job_description_for_ai(job_description)
    normalized_description = re.sub(
        r"\s+",
        " ",
        normalize_job_description_text(job_description).lower(),
    )
    # The previous cleaner could cache an extraction from an empty prompt when
    # a posting began with "About Us". Bump the key to avoid reusing it.
    model = configured_model()
    content_hash = hashlib.sha256(
        (f"jd-v4:{model}:" + normalized_description).encode("utf-8")
    ).hexdigest()

    extracted_data = None if force_refresh else get_cached_extraction(content_hash)

    if extracted_data is None:
        provider = OpenAIProvider()
        extracted_data = ask_openai(build_prompt(cleaned_jd_for_ai), provider=provider)
        save_cached_extraction(
            content_hash,
            model=provider.model,
            extracted_data=extracted_data,
            schema_version="3",
        )

    return clean_extracted_data(extracted_data, job_description)


# ---------------------------------------------------------------------
# 11. Date Helper
# ---------------------------------------------------------------------

def add_business_days(start_date, business_days=5):
    current_date = start_date
    added_days = 0

    while added_days < business_days:
        current_date += timedelta(days=1)

        if current_date.weekday() < 5:
            added_days += 1

    return current_date


# ---------------------------------------------------------------------
# 12. Database Insert Helpers
# ---------------------------------------------------------------------

def insert_items(cursor, job_id, item_type, items):
    """
    Keeps the old job_items table working for backward compatibility.
    """
    for item in items:
        if item and str(item).strip():
            cursor.execute(
                """
                INSERT INTO job_items (job_id, item_type, item_value)
                VALUES (?, ?, ?)
                """,
                (job_id, item_type, str(item).strip()),
            )

def _evidence_snippet(source_text: str, phrase: str) -> str:
    source_text = str(source_text or "")
    phrase = str(phrase or "").strip()
    if not source_text or not phrase:
        return ""
    start = source_text.lower().find(phrase.lower())
    if start < 0:
        return ""
    left = max(source_text.rfind(".", 0, start) + 1, start - 80)
    right_boundary = source_text.find(".", start + len(phrase))
    right = min(len(source_text), right_boundary + 1 if right_boundary >= 0 else start + 180)
    return " ".join(source_text[left:right].strip().split())


def insert_structured_skills(cursor, job_id, skills, created_at, source_text=""):
    """
    Inserts structured skills into the new job_skills table.
    """
    if not isinstance(skills, list):
        return

    seen_skills = set()

    for skill in skills:
        if not isinstance(skill, dict):
            continue

        raw_skill = clean_text_value(skill.get("raw_skill"))
        specific_skill = clean_text_value(skill.get("specific_skill"))
        skill_basket = clean_skill_basket(skill.get("skill_basket"))
        evidence_text = clean_text_value(skill.get("evidence_text")) or _evidence_snippet(
            source_text,
            raw_skill or specific_skill,
        )
        requirement_level = clean_requirement_level(skill.get("requirement_level"))
        confidence = float(skill.get("confidence", 0.75 if evidence_text else 0.45))

        if not specific_skill:
            specific_skill = raw_skill

        if not specific_skill:
            continue

        dedupe_key = (
            specific_skill.lower(),
            skill_basket.lower(),
        )

        if dedupe_key in seen_skills:
            continue

        seen_skills.add(dedupe_key)

        cursor.execute(
            """
            INSERT INTO job_skills
            (
                job_id,
                raw_skill,
                specific_skill,
                skill_basket,
                evidence_text,
                requirement_level,
                confidence,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                raw_skill,
                specific_skill,
                skill_basket,
                evidence_text,
                requirement_level,
                confidence,
                created_at,
            ),
        )


def insert_structured_certifications(cursor, job_id, certifications, created_at, source_text=""):
    """
    Inserts structured certifications into the new job_certifications table.

    One certification may relate to multiple baskets, so this saves one row
    per related basket.
    """
    if not isinstance(certifications, list):
        return

    seen_certifications = set()

    for cert in certifications:
        if not isinstance(cert, dict):
            continue

        raw_certification = clean_text_value(cert.get("raw_certification"))
        certification_name = clean_text_value(cert.get("certification_name"))
        certification_short_name = clean_text_value(cert.get("certification_short_name"))
        requirement_level = clean_requirement_level(cert.get("requirement_level"))
        evidence_text = clean_text_value(cert.get("evidence_text")) or _evidence_snippet(
            source_text,
            raw_certification or certification_short_name or certification_name,
        )
        confidence = float(cert.get("confidence", 0.75 if evidence_text else 0.45))

        if not certification_name and not certification_short_name and raw_certification:
            normalized_cert = normalize_certification(raw_certification)
            certification_name = normalized_cert["certification_name"]
            certification_short_name = normalized_cert["certification_short_name"]
            related_baskets = normalized_cert["related_baskets"]
        else:
            related_baskets = cert.get("related_baskets", [])

        if not certification_name:
            certification_name = certification_short_name or raw_certification

        if not certification_short_name:
            certification_short_name = certification_name

        if not certification_name:
            continue

        if not isinstance(related_baskets, list) or not related_baskets:
            related_baskets = ["Other"]

        for basket in related_baskets:
            related_basket = clean_skill_basket(basket)

            dedupe_key = (
                certification_short_name.lower(),
                certification_name.lower(),
                related_basket.lower(),
            )

            if dedupe_key in seen_certifications:
                continue

            seen_certifications.add(dedupe_key)

            cursor.execute(
                """
                INSERT INTO job_certifications
                (
                    job_id,
                    raw_certification,
                    certification_name,
                    certification_short_name,
                    related_basket,
                    requirement_level,
                    evidence_text,
                    confidence,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    raw_certification,
                    certification_name,
                    certification_short_name,
                    related_basket,
                    requirement_level,
                    evidence_text,
                    confidence,
                    created_at,
                ),
            )

def save_analyzed_application(
    extracted_data,
    date_applied,
    follow_up_date,
    contact_name,
    contact_number,
    current_status,
    notes,
    job_description="",
    contact_email="",
    contact_role="",
    source_url="",
    location="",
    salary_range="",
    work_mode="",
    application_source="",
    resume_version="",
    cover_letter_status="Not started",
    rejected_reason="",
    interview_date="",
    interview_stage="",
    offer_amount="",
    offer_date="",
):
    """
    Saves an analyzed job, structured intelligence, and application metadata.

    The raw description is retained so the user can review the source later,
    while the legacy job_items rows remain for compatibility with old reports.
    """

    extracted_data = clean_extracted_data(extracted_data)

    connection = get_connection()
    try:
        cursor = connection.cursor()

        company = extracted_data.get("company", "").strip()
        job_title = extracted_data.get("job_title", "").strip()
        domain = extracted_data.get("domain", "").strip()

        source_file = f"streamlit_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized_description = re.sub(
            r"\s+",
            " ",
            normalize_job_description_text(job_description).lower(),
        )
        content_hash = (
            hashlib.sha256(normalized_description.encode("utf-8")).hexdigest()
            if normalized_description
            else ""
        )
        extraction_model = configured_model()

        cursor.execute(
            """
            INSERT INTO jobs
            (
                company, recruiter_name, parent_company, end_client_name,
                end_client_industry, posting_type, job_title, domain, source_file, created_at,
                raw_description, source_url, location, salary_range, work_mode,
                application_source, content_hash, extraction_model,
                extraction_version, analyzed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                extracted_data.get("recruiter_name", "").strip(),
                extracted_data.get("parent_company", "").strip(),
                extracted_data.get("end_client_name", "").strip(),
                extracted_data.get("end_client_industry", "").strip(),
                extracted_data.get("posting_type", "").strip(),
                job_title,
                domain,
                source_file,
                created_at,
                job_description,
                source_url,
                location,
                salary_range,
                work_mode,
                application_source,
                content_hash,
                extraction_model,
                "2",
                created_at,
            ),
        )

        job_id = cursor.lastrowid

        insert_items(
            cursor,
            job_id,
            "technical_skill",
            extracted_data.get("technical_skills", []),
        )
        insert_items(
            cursor,
            job_id,
            "soft_skill",
            extracted_data.get("soft_skills", []),
        )
        insert_items(
            cursor,
            job_id,
            "tool_platform",
            extracted_data.get("tools_platforms", []),
        )
        insert_items(
            cursor,
            job_id,
            "certification",
            extracted_data.get("certifications", []),
        )
        insert_items(
            cursor,
            job_id,
            "domain_specific_skill",
            extracted_data.get("domain_specific_skills", []),
        )
        insert_items(
            cursor,
            job_id,
            "responsibility",
            extracted_data.get("responsibilities", []),
        )
        insert_structured_skills(
            cursor,
            job_id,
            extracted_data.get("structured_skills", []),
            created_at,
            job_description,
        )

        insert_structured_certifications(
            cursor,
            job_id,
            extracted_data.get("structured_certifications", []),
            created_at,
            job_description,
        )

        cursor.execute(
            """
            INSERT INTO applications
            (
                job_id,
                company,
                job_title,
                domain,
                source_file,
                date_applied,
                follow_up_date,
                contact_name,
                contact_number,
                contact_email,
                contact_role,
                source_url,
                location,
                salary_range,
                work_mode,
                application_source,
                resume_version,
                cover_letter_status,
                rejected_reason,
                interview_date,
                interview_stage,
                offer_amount,
                offer_date,
                current_status,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, company, job_title, domain, source_file, str(date_applied),
                str(follow_up_date), contact_name, contact_number, contact_email,
                contact_role, source_url, location, salary_range, work_mode,
                application_source, resume_version, cover_letter_status,
                rejected_reason, interview_date, interview_stage, offer_amount,
                offer_date, current_status, notes, created_at,
            ),
        )

        application_id = cursor.lastrowid
        record_status_change(application_id, current_status, connection=connection)
        if follow_up_date:
            record_follow_up_event(
                application_id,
                event_type="scheduled",
                scheduled_for=follow_up_date,
                connection=connection,
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ---------------------------------------------------------------------
# 13. Local Test Block
# ---------------------------------------------------------------------

if __name__ == "__main__":
    test_jd = """
    At Capgemini Engineering, the world leader in engineering services, we bring together a global team of engineers, scientists, and architects to help the world’s most innovative companies unleash their potential.

    Your role

    As an IP Network Engineer, you will be responsible for designing, implementing, and managing IP networks within the telecom domain.

    You will play a key role in:

    Planning, designing, and deploying IP networks in the telecom domain.
    Configuring and managing routers, switches, firewalls, and other network devices.
    Applying and maintaining security policies, including firewalls, intrusion detection systems (IDS), and network access control (NAC).
    Diagnosing and resolving network issues to maintain stability and performance.
    Creating and maintaining documentation for network configurations, procedures, and policies, aligned with industry standards.
    Auditing and managing IP addresses to ensure proper allocation and usage.
    Conducting regular maintenance, upgrades, and patching to enhance system stability and security.

    Your profile

    A bachelor’s degree or tertiary qualification in computer science, telecommunications, engineering, or a related field.
    Relevant industry certifications such as Cisco (CCIE, CCNA, CCNP) are highly valued.
    Strong understanding of IP protocols including OSPF and BGP.
    Experience designing and implementing telecom network architectures, primarily IP-based mobile core network.
    Familiarity with data center fabric technologies including ACI and EVPN-VXLAN.
    Design and configuration of telco grade firewalls and security policy management, preferably Fortinet, F5 and Check Point firewalls.
    Proven ability to diagnose and resolve network issues effectively.
    Understanding of network security principles and technologies.
    """

    result = analyze_jd_with_openai(test_jd)
    print(json.dumps(result, indent=2))
