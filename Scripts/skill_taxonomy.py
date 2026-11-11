# Scripts/skill_taxonomy.py

"""
Central skill and certification taxonomy for the Local AI Career Assistant.

This file defines the approved skill baskets used by the AI extraction layer.
The LLM should only classify skills into these baskets.

If no suitable basket is found, the AI should use "Other".

The taxonomy is based on real job descriptions used for IT Support, Service Desk,
Desktop Support, MSP, Junior Network Support, Cloud Support, and related roles.
"""


# ---------------------------------------------------------------------
# 1. Approved Skill Baskets
# ---------------------------------------------------------------------

ALLOWED_SKILL_BASKETS = [
    "Microsoft 365 Administration",
    "Microsoft Entra ID & Identity",
    "Active Directory",
    "Microsoft Intune & Endpoint Management",
    "Windows Endpoint Support",
    "Service Desk & ITSM",
    "Documentation & Communication",
    "Hardware & Field Support",
    "General Network Fundamentals",
    "Cisco Routing & Switching",
    "Wireless / WLAN",
    "SD-WAN & Enterprise WAN",
    "Voice / VoIP Networking",
    "Firewall & Network Security",
    "Cybersecurity Fundamentals",
    "Azure Cloud",
    "Azure Networking",
    "Linux & Server Support",
    "Virtualization",
    "Backup & Storage",
    "Application / SaaS Support",
    "Scripting & Automation",
    "AI & Digital Productivity",
    "Other",
]


# User-facing canonical names for common extraction variations. Raw values are
# retained in the database; these mappings only control grouped presentation.
SKILL_ALIAS_GROUPS = {
    "Microsoft 365": {
        "microsoft 365",
        "microsoft office 365",
        "office 365",
        "office365",
        "m365",
    },
    "Microsoft Entra ID": {
        "microsoft entra id",
        "entra id",
        "entra",
        "azure ad",
        "microsoft azure ad",
        "azure active directory",
    },
    "Active Directory": {
        "active directory",
        "windows active directory",
        "ad administration",
        "active directory administration",
    },
    "Cisco IOS": {
        "cisco ios",
        "ios",
        "cisco ios configuration",
    },
    "Network Troubleshooting": {
        "network troubleshooting",
        "troubleshooting networks",
        "network fault finding",
        "network fault-finding",
    },
    "Routing and Switching": {
        "routing and switching",
        "routing & switching",
        "cisco routing and switching",
        "cisco routing & switching",
    },
    "Microsoft Intune": {
        "microsoft intune",
        "intune",
        "microsoft endpoint manager",
        "endpoint manager",
    },
    "ServiceNow": {
        "servicenow",
        "service now",
    },
}


CERTIFICATION_ALIAS_GROUPS = {
    "CompTIA A+": {
        "a+",
        "a +",
        "comptia a+",
        "comptia a +",
    },
    "Cisco Certified Network Associate": {
        "ccna",
        "cisco ccna",
        "cisco certified network associate",
    },
    "Cisco Certified Network Professional": {
        "ccnp",
        "cisco ccnp",
        "cisco certified network professional",
    },
    "Cisco Certified Internetwork Expert": {
        "ccie",
        "cisco ccie",
        "cisco certified internetwork expert",
    },
    "ITIL Foundation": {
        "itil",
        "itil foundation",
        "itil v4",
        "itil 4",
    },
    "Security+": {
        "security+",
        "security plus",
        "comptia security+",
    },
}


# ---------------------------------------------------------------------
# 2. Skill Basket Hints
# ---------------------------------------------------------------------

SKILL_HINTS = {
    "Microsoft 365 Administration": [
        "Microsoft 365",
        "M365",
        "Office 365",
        "Outlook",
        "Exchange",
        "Exchange Online",
        "Microsoft Teams",
        "Teams",
        "SharePoint",
        "SharePoint Online",
        "OneDrive",
        "OneDrive for Business",
        "mailbox",
        "mailbox support",
        "calendar issues",
        "distribution list",
        "M365 admin center",
        "Microsoft 365 admin center",
        "Teams configuration",
    ],

    "Microsoft Entra ID & Identity": [
        "Microsoft Entra ID",
        "Entra ID",
        "Azure AD",
        "identity",
        "identity management",
        "access management",
        "user management",
        "user administration",
        "MFA",
        "Multi-Factor Authentication",
        "Conditional Access",
        "group-based access",
        "group access",
        "sign-in logs",
        "sign-in troubleshooting",
        "authentication",
        "SSO",
        "single sign-on",
        "access troubleshooting",
    ],

    "Active Directory": [
        "Active Directory",
        "AD",
        "domain accounts",
        "domain controller",
        "Group Policy",
        "GPO",
        "OU",
        "organizational unit",
        "password resets",
        "account setup",
        "user account management",
        "group administration",
        "onboarding",
        "offboarding",
    ],

    "Microsoft Intune & Endpoint Management": [
        "Microsoft Intune",
        "Intune",
        "Microsoft Endpoint Manager",
        "Endpoint Manager",
        "endpoint management",
        "MDM",
        "mobile device management",
        "MAM",
        "mobile application management",
        "Windows Autopilot",
        "Autopilot",
        "device compliance",
        "compliance policies",
        "configuration profiles",
        "endpoint security",
    ],

    "Windows Endpoint Support": [
        "Windows 10",
        "Windows 11",
        "Windows endpoint",
        "Windows support",
        "desktop operating system",
        "desktop support",
        "laptop support",
        "SOE",
        "standard operating environment",
        "imaging",
        "device imaging",
        "device deployment",
        "Windows troubleshooting",
        "BitLocker",
        "patching",
        "profile issues",
        "driver issues",
    ],

    "Service Desk & ITSM": [
        "service desk",
        "helpdesk",
        "ITSM",
        "ticketing",
        "ticket logging",
        "ticket triage",
        "incident management",
        "request management",
        "service request management",
        "problem management",
        "change management",
        "SLA",
        "SLA compliance",
        "escalation",
        "L1 support",
        "L2 support",
        "Level 1 support",
        "Level 2 support",
        "Jira",
        "Jira Service Desk",
        "Jira Service Management",
        "ServiceNow",
        "Service Central",
        "ITIL",
    ],

    "Documentation & Communication": [
        "documentation",
        "technical documentation",
        "knowledge base",
        "knowledge articles",
        "runbooks",
        "troubleshooting notes",
        "handover notes",
        "customer communication",
        "technical communication",
        "stakeholder communication",
        "customer service",
        "process documentation",
        "Visio",
        "HLD",
        "LLD",
        "high-level design",
        "low-level design",
    ],

    "Hardware & Field Support": [
        "laptops",
        "desktops",
        "printers",
        "printer support",
        "mobile devices",
        "meeting room technology",
        "meeting room tech",
        "AV support",
        "audio visual support",
        "onsite support",
        "field support",
        "field technician",
        "remote support",
        "device rollout",
        "hardware troubleshooting",
        "asset management",
        "asset records",
        "CMDB",
        "driver's licence",
        "customer site visits",
    ],

    "General Network Fundamentals": [
        "TCP/IP",
        "TCP",
        "UDP",
        "DNS",
        "DHCP",
        "IP addressing",
        "subnetting",
        "subnets",
        "LAN",
        "WAN",
        "LAN/WAN",
        "basic Wi-Fi troubleshooting",
        "VPN",
        "NAT",
        "ping",
        "traceroute",
        "network troubleshooting",
        "basic networking",
        "fault isolation",
        "IPv4",
        "IPv6",
    ],

    "Cisco Routing & Switching": [
        "Cisco",
        "Cisco IOS",
        "routing",
        "switching",
        "router",
        "switch",
        "VLAN",
        "VLANs",
        "trunk",
        "trunks",
        "VLAN trunking",
        "inter-VLAN routing",
        "STP",
        "Spanning Tree Protocol",
        "OSPF",
        "BGP",
        "EIGRP",
        "static routing",
        "port-channel",
        "EtherChannel",
        "ACL",
        "routing tables",
        "Cisco Catalyst",
    ],

    "Wireless / WLAN": [
        "Wi-Fi",
        "WLAN",
        "wireless",
        "wireless LAN",
        "wireless troubleshooting",
        "access point",
        "access points",
        "AP",
        "Cisco wireless",
        "WLC",
        "wireless controller",
        "SSID",
        "SSIDs",
        "802.11",
        "802.11 security",
        "wireless security",
        "wireless topology",
        "WLAN topologies",
    ],

    "SD-WAN & Enterprise WAN": [
        "SD-WAN",
        "Cisco Viptela",
        "Viptela",
        "Meraki",
        "Cisco Meraki",
        "VMware Velocloud",
        "Velocloud",
        "Prisma SD-WAN",
        "Palo Alto Prisma SD-WAN",
        "MPLS",
        "VRF",
        "QoS",
        "Quality of Service",
        "traffic shaping",
        "enterprise WAN",
        "WAN activation",
        "network activation",
    ],

    "Voice / VoIP Networking": [
        "VoIP",
        "Voice over IP",
        "SIP",
        "SIP trunks",
        "SIP trunking",
        "SIP traces",
        "SIP trace analysis",
        "telephony",
        "telephony fundamentals",
        "RTP",
        "voice gateway",
        "Microsoft Teams Phone",
        "Teams Phone",
        "Cisco BroadWorks",
        "BroadWorks",
        "BroadSoft",
        "hunt groups",
        "auto-attendants",
        "IVR",
        "call queues",
        "CDR",
        "CDR lookup",
        "CDR7",
        "CommPilot",
        "Unified Communications",
        "UC support",
    ],

    "Firewall & Network Security": [
        "firewall",
        "firewalls",
        "firewall policies",
        "firewall rules",
        "security policies",
        "network security",
        "device hardening",
        "Fortinet",
        "FortiGate",
        "FortiManager",
        "FortiAnalyzer",
        "FortiClient",
        "Palo Alto",
        "Palo Alto Firewall",
        "PAN-OS",
        "GlobalProtect",
        "Panorama",
        "SonicWall",
        "Sophos Firewall",
        "VPN firewall",
        "IPsec VPN",
        "SSL VPN",
    ],

    "Cybersecurity Fundamentals": [
        "cybersecurity",
        "security awareness",
        "phishing",
        "phishing awareness",
        "suspicious activity",
        "suspicious activity escalation",
        "security escalation",
        "security incident",
        "security incident awareness",
        "access control",
        "least privilege",
        "MFA",
        "vulnerability",
        "vulnerability awareness",
        "risk awareness",
        "frontline security",
        "endpoint security",
        "EDR",
        "SIEM",
        "Splunk",
    ],

    "Azure Cloud": [
        "Azure",
        "Microsoft Azure",
        "Azure Portal",
        "Azure administration",
        "Azure admin",
        "cloud services",
        "cloud administration",
        "resource groups",
        "Azure subscriptions",
        "Azure Storage",
        "Storage Accounts",
        "storage concepts",
        "Azure Virtual Machines",
        "Azure VM",
        "Azure Monitor",
        "Azure Backup",
    ],

    "Azure Networking": [
        "Azure networking",
        "Azure Virtual Network",
        "VNet",
        "virtual networks",
        "cloud networking",
        "cloud connectivity",
        "NSG",
        "Network Security Group",
        "Azure VPN Gateway",
        "Azure Firewall",
        "ExpressRoute",
        "Azure Load Balancer",
        "Application Gateway",
    ],

    "Linux & Server Support": [
        "Linux",
        "Linux server",
        "server support",
        "server maintenance",
        "scheduled maintenance",
        "production server",
        "server patching",
        "patching",
        "backend logs",
        "log analysis",
        "Bash",
        "shell",
        "SSH",
        "Ubuntu",
        "Debian",
        "Red Hat",
        "CentOS",
        "systemd",
        "cron",
    ],

    "Virtualization": [
        "virtualization",
        "virtual machines",
        "VM",
        "VMs",
        "VMware",
        "VMware ESXi",
        "ESXi",
        "vSphere",
        "Hyper-V",
        "VirtualBox",
        "virtual server",
    ],

    "Backup & Storage": [
        "backup",
        "backups",
        "restore",
        "disaster recovery",
        "DR",
        "storage",
        "storage accounts",
        "SAN",
        "NAS",
        "RAID",
        "snapshot",
        "Veeam",
        "Azure Backup",
    ],

    "Application / SaaS Support": [
        "application support",
        "SaaS support",
        "software support",
        "CRM",
        "Salesforce",
        "Salesforce support",
        "application incidents",
        "SQL",
        "SQL basics",
        "database support",
        "Azure DevOps",
        "business applications",
        "line-of-business applications",
    ],

    "Scripting & Automation": [
        "PowerShell",
        "Python",
        "Bash",
        "scripting",
        "automation",
        "workflow automation",
        "automation rules",
        "process automation",
        "API",
        "JSON",
        "YAML",
        "Ansible",
        "service desk automation",
    ],

    "AI & Digital Productivity": [
        "AI tools",
        "AI-first",
        "responsible AI use",
        "digital productivity",
        "process improvement",
        "continuous improvement",
        "automation initiatives",
        "knowledge base improvement",
        "service desk improvement",
        "workflow improvement",
        "local AI",
        "AI awareness",
    ],

    "Other": [],
}


# ---------------------------------------------------------------------
# 3. Certification Mappings
# ---------------------------------------------------------------------

CERTIFICATION_MAPPINGS = {
    "ITIL": {
        "certification_name": "ITIL Foundation",
        "certification_short_name": "ITIL",
        "related_baskets": ["Service Desk & ITSM"],
    },
    "ITIL Foundation": {
        "certification_name": "ITIL Foundation",
        "certification_short_name": "ITIL",
        "related_baskets": ["Service Desk & ITSM"],
    },

    "CCNA": {
        "certification_name": "Cisco Certified Network Associate",
        "certification_short_name": "CCNA",
        "related_baskets": [
            "General Network Fundamentals",
            "Cisco Routing & Switching",
            "Wireless / WLAN",
        ],
    },
    "Cisco Certified Network Associate": {
        "certification_name": "Cisco Certified Network Associate",
        "certification_short_name": "CCNA",
        "related_baskets": [
            "General Network Fundamentals",
            "Cisco Routing & Switching",
            "Wireless / WLAN",
        ],
    },

    "CCNP": {
        "certification_name": "Cisco Certified Network Professional",
        "certification_short_name": "CCNP",
        "related_baskets": [
            "Cisco Routing & Switching",
            "SD-WAN & Enterprise WAN",
        ],
    },
    "Cisco Certified Network Professional": {
        "certification_name": "Cisco Certified Network Professional",
        "certification_short_name": "CCNP",
        "related_baskets": [
            "Cisco Routing & Switching",
            "SD-WAN & Enterprise WAN",
        ],
    },

    "Cisco Certification": {
        "certification_name": "Cisco Certification",
        "certification_short_name": "Cisco",
        "related_baskets": ["Cisco Routing & Switching"],
    },

    "Cisco / BroadWorks Associate Certification": {
        "certification_name": "Cisco / BroadWorks Associate Certification",
        "certification_short_name": "Cisco/BroadWorks",
        "related_baskets": ["Voice / VoIP Networking"],
    },
    "BroadWorks Certification": {
        "certification_name": "BroadWorks Certification",
        "certification_short_name": "BroadWorks",
        "related_baskets": ["Voice / VoIP Networking"],
    },

    "CompTIA A+": {
        "certification_name": "CompTIA A+",
        "certification_short_name": "A+",
        "related_baskets": [
            "Windows Endpoint Support",
            "Hardware & Field Support",
            "Service Desk & ITSM",
        ],
    },
    "A+": {
        "certification_name": "CompTIA A+",
        "certification_short_name": "A+",
        "related_baskets": [
            "Windows Endpoint Support",
            "Hardware & Field Support",
            "Service Desk & ITSM",
        ],
    },

    "CompTIA Network+": {
        "certification_name": "CompTIA Network+",
        "certification_short_name": "Network+",
        "related_baskets": ["General Network Fundamentals"],
    },
    "Network+": {
        "certification_name": "CompTIA Network+",
        "certification_short_name": "Network+",
        "related_baskets": ["General Network Fundamentals"],
    },

    "CompTIA Security+": {
        "certification_name": "CompTIA Security+",
        "certification_short_name": "Security+",
        "related_baskets": [
            "Cybersecurity Fundamentals",
            "Firewall & Network Security",
        ],
    },
    "Security+": {
        "certification_name": "CompTIA Security+",
        "certification_short_name": "Security+",
        "related_baskets": [
            "Cybersecurity Fundamentals",
            "Firewall & Network Security",
        ],
    },

    "MS-900": {
        "certification_name": "Microsoft 365 Certified: Fundamentals",
        "certification_short_name": "MS-900",
        "related_baskets": [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ],
    },
    "Microsoft 365 Fundamentals": {
        "certification_name": "Microsoft 365 Certified: Fundamentals",
        "certification_short_name": "MS-900",
        "related_baskets": [
            "Microsoft 365 Administration",
            "Microsoft Entra ID & Identity",
        ],
    },

    "AZ-900": {
        "certification_name": "Microsoft Azure Fundamentals",
        "certification_short_name": "AZ-900",
        "related_baskets": ["Azure Cloud"],
    },
    "Microsoft Azure Fundamentals": {
        "certification_name": "Microsoft Azure Fundamentals",
        "certification_short_name": "AZ-900",
        "related_baskets": ["Azure Cloud"],
    },

    "AZ-104": {
        "certification_name": "Microsoft Azure Administrator",
        "certification_short_name": "AZ-104",
        "related_baskets": [
            "Azure Cloud",
            "Azure Networking",
            "Scripting & Automation",
        ],
    },
    "Microsoft Azure Administrator": {
        "certification_name": "Microsoft Azure Administrator",
        "certification_short_name": "AZ-104",
        "related_baskets": [
            "Azure Cloud",
            "Azure Networking",
            "Scripting & Automation",
        ],
    },

    "MD-102": {
        "certification_name": "Microsoft Endpoint Administrator",
        "certification_short_name": "MD-102",
        "related_baskets": [
            "Microsoft Intune & Endpoint Management",
            "Windows Endpoint Support",
        ],
    },
    "Microsoft Endpoint Administrator": {
        "certification_name": "Microsoft Endpoint Administrator",
        "certification_short_name": "MD-102",
        "related_baskets": [
            "Microsoft Intune & Endpoint Management",
            "Windows Endpoint Support",
        ],
    },

    "SC-900": {
        "certification_name": "Microsoft Security, Compliance, and Identity Fundamentals",
        "certification_short_name": "SC-900",
        "related_baskets": [
            "Microsoft Entra ID & Identity",
            "Cybersecurity Fundamentals",
        ],
    },

    "Teams Essentials": {
        "certification_name": "Microsoft Teams / Teams Phone Training",
        "certification_short_name": "Teams Essentials",
        "related_baskets": [
            "Microsoft 365 Administration",
            "Voice / VoIP Networking",
        ],
    },

    "Palo Alto": {
        "certification_name": "Palo Alto Firewall Certification",
        "certification_short_name": "Palo Alto",
        "related_baskets": [
            "Firewall & Network Security",
            "SD-WAN & Enterprise WAN",
        ],
    },
    "Palo Alto Firewall Certification": {
        "certification_name": "Palo Alto Firewall Certification",
        "certification_short_name": "Palo Alto",
        "related_baskets": [
            "Firewall & Network Security",
            "SD-WAN & Enterprise WAN",
        ],
    },

    "Fortinet NSE": {
        "certification_name": "Fortinet NSE Certification",
        "certification_short_name": "Fortinet NSE",
        "related_baskets": ["Firewall & Network Security"],
    },
    "FCP": {
        "certification_name": "Fortinet Certified Professional",
        "certification_short_name": "FCP",
        "related_baskets": ["Firewall & Network Security"],
    },

    "JNCIA": {
        "certification_name": "Juniper Networks Certified Associate",
        "certification_short_name": "JNCIA",
        "related_baskets": [
            "General Network Fundamentals",
            "SD-WAN & Enterprise WAN",
        ],
    },

    "SD-WAN Vendor Certification": {
        "certification_name": "SD-WAN Vendor Certification",
        "certification_short_name": "SD-WAN Certs",
        "related_baskets": ["SD-WAN & Enterprise WAN"],
    },

    "Vendor Certifications": {
        "certification_name": "Vendor Certifications",
        "certification_short_name": "Vendor Certs",
        "related_baskets": [
            "Microsoft 365 Administration",
            "Azure Cloud",
            "Cisco Routing & Switching",
            "Cybersecurity Fundamentals",
            "Firewall & Network Security",
        ],
    },
}


# ---------------------------------------------------------------------
# 4. Career Skill Patterns
# ---------------------------------------------------------------------

CAREER_SKILL_PATTERNS = {
    "Microsoft 365 + Windows + Service Desk": {
        "importance": "Very High",
        "related_baskets": [
            "Microsoft 365 Administration",
            "Windows Endpoint Support",
            "Service Desk & ITSM",
            "Documentation & Communication",
            "Hardware & Field Support",
        ],
        "common_skills": [
            "Microsoft 365",
            "Outlook",
            "Teams",
            "SharePoint",
            "OneDrive",
            "Windows 10/11",
            "laptops",
            "desktops",
            "printers",
            "tickets",
            "SLAs",
            "escalation",
            "documentation",
        ],
    },

    "Entra ID / Active Directory + User Support": {
        "importance": "Very High",
        "related_baskets": [
            "Microsoft Entra ID & Identity",
            "Active Directory",
            "Microsoft 365 Administration",
            "Service Desk & ITSM",
        ],
        "common_skills": [
            "Entra ID",
            "Active Directory",
            "user administration",
            "password resets",
            "MFA",
            "Conditional Access",
            "group access",
            "onboarding",
            "offboarding",
        ],
    },

    "Service Desk + ITSM + Customer Communication": {
        "importance": "Very High",
        "related_baskets": [
            "Service Desk & ITSM",
            "Documentation & Communication",
        ],
        "common_skills": [
            "ticket logging",
            "triage",
            "incident management",
            "request management",
            "Jira",
            "ServiceNow",
            "SLAs",
            "escalation",
            "documentation",
            "knowledge base",
            "customer service",
        ],
    },

    "Networking Fundamentals + Troubleshooting": {
        "importance": "Very High",
        "related_baskets": [
            "General Network Fundamentals",
            "Wireless / WLAN",
        ],
        "common_skills": [
            "TCP/IP",
            "DNS",
            "DHCP",
            "IP addressing",
            "subnetting",
            "LAN/WAN",
            "Wi-Fi",
            "VPN",
            "ping",
            "traceroute",
            "fault isolation",
        ],
    },

    "Cisco Routing/Switching + Enterprise Network Support": {
        "importance": "Medium-High",
        "related_baskets": [
            "Cisco Routing & Switching",
            "General Network Fundamentals",
            "Documentation & Communication",
        ],
        "common_skills": [
            "Cisco",
            "routing",
            "switching",
            "VLANs",
            "trunks",
            "OSPF",
            "BGP",
            "EIGRP",
            "STP",
            "port-channel",
            "network documentation",
        ],
    },

    "SD-WAN + MPLS + Enterprise WAN": {
        "importance": "Medium",
        "related_baskets": [
            "SD-WAN & Enterprise WAN",
            "Cisco Routing & Switching",
            "General Network Fundamentals",
        ],
        "common_skills": [
            "SD-WAN",
            "Viptela",
            "Meraki",
            "Velocloud",
            "Prisma SD-WAN",
            "MPLS",
            "VRF",
            "QoS",
            "traffic shaping",
        ],
    },

    "Voice / VoIP / UC Support": {
        "importance": "Medium",
        "related_baskets": [
            "Voice / VoIP Networking",
            "Microsoft 365 Administration",
            "General Network Fundamentals",
        ],
        "common_skills": [
            "SIP",
            "VoIP",
            "SIP trunks",
            "SIP traces",
            "Teams Phone",
            "Cisco BroadWorks",
            "CDR lookups",
            "hunt groups",
            "auto-attendants",
            "IVR",
        ],
    },

    "Cybersecurity Frontline Awareness": {
        "importance": "High",
        "related_baskets": [
            "Cybersecurity Fundamentals",
            "Microsoft Entra ID & Identity",
            "Service Desk & ITSM",
        ],
        "common_skills": [
            "phishing",
            "suspicious activity",
            "MFA",
            "access control",
            "escalation",
            "security incidents",
            "vulnerability awareness",
        ],
    },

    "Hardware + Field / Onsite Support": {
        "importance": "High",
        "related_baskets": [
            "Hardware & Field Support",
            "Windows Endpoint Support",
            "Documentation & Communication",
        ],
        "common_skills": [
            "laptops",
            "desktops",
            "printers",
            "mobile devices",
            "meeting room tech",
            "onsite visits",
            "driver's licence",
            "customer locations",
        ],
    },

    "Automation + AI + Process Improvement": {
        "importance": "Medium-High",
        "related_baskets": [
            "Scripting & Automation",
            "AI & Digital Productivity",
            "Documentation & Communication",
            "Service Desk & ITSM",
        ],
        "common_skills": [
            "AI tools",
            "automation",
            "service desk improvement",
            "knowledge base",
            "process improvement",
            "workflow automation",
        ],
    },
}


# ---------------------------------------------------------------------
# 5. Helper Functions for AI Prompting
# ---------------------------------------------------------------------

def get_allowed_skill_baskets_text() -> str:
    """
    Returns the allowed skill baskets as a clean bullet list for the LLM prompt.
    """
    return "\n".join(f"- {basket}" for basket in ALLOWED_SKILL_BASKETS)


def get_skill_hints_text() -> str:
    """
    Returns skill basket hints for the LLM prompt.
    These are examples only. The LLM can still classify intelligently,
    but it must stay within the allowed baskets.
    """
    lines = []

    for basket, hints in SKILL_HINTS.items():
        if not hints:
            continue

        hint_text = ", ".join(hints)
        lines.append(f"- {basket}: {hint_text}")

    return "\n".join(lines)


def get_certification_mappings_text() -> str:
    """
    Returns certification mapping examples for the LLM prompt.
    """
    lines = []

    for cert_key, cert_data in CERTIFICATION_MAPPINGS.items():
        baskets = ", ".join(cert_data["related_baskets"])
        lines.append(
            f"- {cert_key}: {cert_data['certification_name']} "
            f"({cert_data['certification_short_name']}) -> {baskets}"
        )

    return "\n".join(lines)


def get_career_patterns_text() -> str:
    """
    Returns recurring career skill patterns for the LLM prompt.
    """
    lines = []

    for pattern_name, pattern_data in CAREER_SKILL_PATTERNS.items():
        baskets = ", ".join(pattern_data["related_baskets"])
        skills = ", ".join(pattern_data["common_skills"])
        importance = pattern_data["importance"]

        lines.append(
            f"- {pattern_name} | Importance: {importance} | "
            f"Related baskets: {baskets} | Common skills: {skills}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------
# 6. Validation and Normalization Helpers
# ---------------------------------------------------------------------

def is_allowed_skill_basket(skill_basket: str) -> bool:
    """
    Checks whether a skill basket is part of the approved taxonomy.
    """
    if not skill_basket:
        return False

    return skill_basket.strip() in ALLOWED_SKILL_BASKETS


def clean_skill_basket(skill_basket: str) -> str:
    """
    Ensures basket values always stay inside the approved taxonomy.
    If the AI returns an invalid basket, this safely converts it to Other.
    """
    if not skill_basket:
        return "Other"

    cleaned = str(skill_basket).strip()

    if cleaned in ALLOWED_SKILL_BASKETS:
        return cleaned

    return "Other"


def clean_text_value(value) -> str:
    """
    Basic text cleanup helper before saving values into SQLite.
    """
    if value is None:
        return ""

    return str(value).strip()


def clean_requirement_level(requirement_level: str) -> str:
    """
    Standardizes requirement level labels.
    """
    if not requirement_level:
        return "Not specified"

    cleaned = str(requirement_level).strip().lower()

    if "required" in cleaned or "mandatory" in cleaned or "mandate" in cleaned:
        return "Required"

    if "preferred" in cleaned or "desirable" in cleaned:
        return "Preferred"

    if "nice" in cleaned or "bonus" in cleaned:
        return "Nice-to-have"

    if "implied" in cleaned:
        return "Implied"

    return "Not specified"


def _normalization_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("–", "-").split())


def normalize_skill_name(raw_skill: str, current_skill: str = "") -> str:
    """Return the canonical display name for a skill variation."""

    candidate = current_skill or raw_skill
    key = _normalization_key(candidate)
    if not key:
        return ""

    for canonical, aliases in SKILL_ALIAS_GROUPS.items():
        if key == _normalization_key(canonical) or key in {
            _normalization_key(alias) for alias in aliases
        }:
            return canonical

    return str(candidate).strip()


def normalize_certification_name(raw_certification: str, current_name: str = "") -> str:
    """Return a canonical certification name for user-facing summaries."""

    candidate = current_name or raw_certification
    key = _normalization_key(candidate)
    if not key:
        return ""

    for canonical, aliases in CERTIFICATION_ALIAS_GROUPS.items():
        if key == _normalization_key(canonical) or key in {
            _normalization_key(alias) for alias in aliases
        }:
            return canonical

    mapped = normalize_certification(candidate)
    return mapped["certification_name"] or str(candidate).strip()


def normalize_certification(raw_certification: str) -> dict:
    """
    Normalizes a raw certification phrase using known certification mappings.

    Returns:
        {
            "certification_name": "...",
            "certification_short_name": "...",
            "related_baskets": [...]
        }
    """
    if not raw_certification:
        return {
            "certification_name": "",
            "certification_short_name": "",
            "related_baskets": ["Other"],
        }

    raw_clean = str(raw_certification).strip()
    raw_lower = raw_clean.lower()

    for cert_key, cert_data in CERTIFICATION_MAPPINGS.items():
        cert_key_lower = cert_key.lower()

        if cert_key_lower in raw_lower or raw_lower in cert_key_lower:
            return {
                "certification_name": cert_data["certification_name"],
                "certification_short_name": cert_data["certification_short_name"],
                "related_baskets": cert_data["related_baskets"],
            }

    return {
        "certification_name": raw_clean,
        "certification_short_name": raw_clean,
        "related_baskets": ["Other"],
    }
