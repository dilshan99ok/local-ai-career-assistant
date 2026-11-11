import sqlite3
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pandas as pd

from App.app_utils import database
from Scripts import ai_helper
from Scripts.resume_helper import extract_resume_skills
from Scripts.resume_import import extract_resume_details, extract_resume_text
from Scripts.resume_export import build_resume_docx, safe_resume_filename
from Scripts.resume_profiles import choose_profile
from Scripts.job_fit import build_job_fit_summary, build_fit_snapshot
from Scripts.job_url import JobPageFetchError, fetch_job_posting
from Scripts.skill_analysis import build_certification_summary, build_skill_demand_summary
from Scripts.tailoring import (
    build_cover_letter_prompt,
    build_follow_up_email_prompt,
    build_resume_tailoring_prompt,
)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "career.db"
        self.database_path_patch = patch.object(database, "DB_PATH", self.db_path)
        self.helper_path_patch = patch.object(ai_helper, "DB_PATH", self.db_path)
        self.database_path_patch.start()
        self.helper_path_patch.start()
        database.initialize_database()

    def tearDown(self):
        self.helper_path_patch.stop()
        self.database_path_patch.stop()
        self.temp_dir.cleanup()

    def test_schema_contains_upgrade_tables(self):
        connection = sqlite3.connect(self.db_path)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        connection.close()

        self.assertIn("application_status_history", tables)
        self.assertIn("follow_up_events", tables)
        self.assertIn("ai_extraction_cache", tables)
        self.assertIn("resume_profiles", tables)
        self.assertIn("application_messages", tables)

    def test_resume_preview_keeps_original_file_and_can_attach_legacy_file(self):
        source = build_resume_docx("# Example CV\nNetwork engineering")
        profile_id = database.save_resume_profile(
            "Example CV", "Example CV\nNetwork engineering", [],
            source_filename="example.docx", source_type="DOCX", source_file=source,
        )
        filename, stored = database.get_resume_source_file(profile_id)
        self.assertEqual(filename, "example.docx")
        self.assertEqual(stored, source)
        self.assertNotIn("source_file", database.get_resume_profiles_df().columns)

        legacy_id = database.save_resume_profile(
            "Older CV", "Example CV", [], source_filename="older.pdf", source_type="PDF",
        )
        self.assertIsNone(database.get_resume_source_file(legacy_id)[1])
        database.attach_resume_source_file(legacy_id, "older.pdf", b"%PDF-test")
        self.assertEqual(database.get_resume_source_file(legacy_id), ("older.pdf", b"%PDF-test"))

    def test_category_base_cvs_and_job_drafts_remain_separate(self):
        network_id = database.save_resume_profile(
            "Networking CV", "BGP routing experience", [{"skill": "BGP"}],
            target_domain="Networking", source_filename="networking.docx",
        )
        support_id = database.save_resume_profile(
            "IT Support CV", "Desktop support experience", [{"skill": "Desktop Support"}],
            target_domain="IT Support", source_filename="support.pdf",
        )
        profiles = database.get_resume_profiles_df()
        self.assertEqual(len(profiles), 2)
        self.assertEqual(int(choose_profile(profiles, "Networking")["id"]), network_id)
        self.assertEqual(int(choose_profile(profiles, "IT Support")["id"]), support_id)
        self.assertEqual(int(profiles[profiles["is_active"] == 1].iloc[0]["id"]), network_id)

        version_id = database.save_resume_version(
            "Network Engineer draft", "# Network Engineer\n- BGP routing experience",
            profile_id=network_id, source_type="tailored", target_job_id=12,
        )
        versions = database.get_resume_versions_df()
        self.assertEqual(int(versions.iloc[0]["id"]), version_id)
        self.assertEqual(versions.iloc[0]["source_profile_name"], "Networking CV")
        self.assertEqual(versions.iloc[0]["target_job_id"], 12)
        self.assertEqual(
            database.get_resume_profiles_df().set_index("id").loc[network_id, "resume_text"],
            "BGP routing experience",
        )

        network_skill = pd.DataFrame([{
            "raw_skill": "bgp", "specific_skill": "BGP",
            "skill_basket": "Cisco Routing & Switching",
        }])
        self.assertEqual(build_fit_snapshot(network_skill, profiles, "Networking")["score"], 100)
        self.assertEqual(build_fit_snapshot(network_skill, profiles, "IT Support")["score"], 0)

    def test_remove_base_cv_keeps_job_draft_and_promotes_another_default(self):
        first_id = database.save_resume_profile(
            "Networking CV", "BGP routing", [], target_domain="Networking"
        )
        second_id = database.save_resume_profile(
            "Support CV", "Desktop support", [], target_domain="IT Support"
        )
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "INSERT INTO applications (company, job_title, current_status) VALUES (?, ?, ?)",
            ("Example", "Network Engineer", "Applied"),
        )
        application_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.commit()
        connection.close()
        version_id = database.save_resume_version(
            "Network draft", "# Network Engineer\nBGP routing", profile_id=first_id,
            source_type="tailored", target_job_id=42, application_id=application_id,
        )

        self.assertTrue(database.delete_resume_profile(first_id))
        self.assertFalse(database.delete_resume_profile(first_id))
        profiles = database.get_resume_profiles_df()
        self.assertEqual(profiles["id"].tolist(), [second_id])
        self.assertEqual(int(profiles.iloc[0]["is_active"]), 1)
        versions = database.get_resume_versions_df()
        self.assertEqual(int(versions.iloc[0]["id"]), version_id)
        self.assertTrue(pd.isna(versions.iloc[0]["profile_id"]))
        self.assertEqual(int(versions.iloc[0]["target_job_id"]), 42)
        connection = sqlite3.connect(self.db_path)
        linked = connection.execute(
            "SELECT resume_version_id FROM applications WHERE id = ?", (application_id,)
        ).fetchone()[0]
        connection.close()
        self.assertEqual(linked, version_id)

    def test_reviewed_resume_exports_to_editable_docx(self):
        content = "# Network Engineer\n## Experience\n- BGP routing experience"
        docx = build_resume_docx(content)
        self.assertEqual(
            extract_resume_text("tailored.docx", docx),
            "Network Engineer\nExperience\n• BGP routing experience",
        )
        self.assertEqual(safe_resume_filename("Network Engineer / Symbio"), "Network_Engineer_Symbio.docx")

    def test_job_detail_skills_include_fit_columns(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("INSERT INTO jobs (job_title) VALUES (?)", ("Network Engineer",))
        job_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.execute(
            "INSERT INTO job_skills (job_id, raw_skill, specific_skill, skill_basket, requirement_level) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_id, "bgp", "BGP", "Cisco Routing & Switching", "Required"),
        )
        connection.commit()
        connection.close()

        skills = database.get_job_skills_for_job_df(job_id)
        self.assertEqual(skills.iloc[0]["requirement_level"], "Required")
        self.assertIn("evidence_text", skills.columns)

    def test_save_application_writes_richer_record_and_history(self):
        extracted = {
            "company": "Example Networks",
            "job_title": "Junior Network Engineer",
            "domain": "Networking",
            "technical_skills": ["Routing"],
            "soft_skills": [],
            "tools_platforms": ["Cisco IOS"],
            "certifications": [],
            "domain_specific_skills": ["Routing"],
            "responsibilities": ["Support network operations"],
            "structured_skills": [
                {
                    "raw_skill": "routing",
                    "specific_skill": "Routing",
                    "skill_basket": "Cisco Routing & Switching",
                }
            ],
            "structured_certifications": [],
        }

        ai_helper.save_analyzed_application(
            extracted_data=extracted,
            date_applied="2026-11-03",
            follow_up_date="2026-11-10",
            contact_name="Recruiter",
            contact_number="000",
            current_status="Applied",
            notes="Test record",
            job_description="Junior Network Engineer role supporting enterprise networks.",
            contact_email="recruiter@example.com",
            contact_role="Recruiter",
            source_url="https://example.com/job",
            location="Sydney",
            salary_range="$80,000",
            work_mode="Hybrid",
            application_source="Company site",
            resume_version="Network resume",
            cover_letter_status="Submitted",
        )

        connection = sqlite3.connect(self.db_path)
        application = connection.execute(
            "SELECT job_title, contact_email, source_url, work_mode FROM applications"
        ).fetchone()
        status_history = connection.execute(
            "SELECT status FROM application_status_history"
        ).fetchone()
        follow_up_history = connection.execute(
            "SELECT event_type, scheduled_for FROM follow_up_events"
        ).fetchone()
        connection.close()

        self.assertEqual(application, (
            "Junior Network Engineer",
            "recruiter@example.com",
            "https://example.com/job",
            "Hybrid",
        ))
        self.assertEqual(status_history[0], "Applied")
        self.assertEqual(follow_up_history, ("scheduled", "2026-11-10"))

    def test_resume_skill_matching_is_local_and_canonical(self):
        skills = extract_resume_skills(
            "Supported Microsoft 365, Active Directory and Cisco routing."
        )
        skill_names = {item["skill"] for item in skills}

        self.assertIn("Microsoft 365", skill_names)
        self.assertIn("Active Directory", skill_names)
        self.assertTrue(any(item["basket"] == "Cisco Routing & Switching" for item in skills))

    def test_resume_file_import_extracts_text_and_details(self):
        text = (
            "Dilshan Perera\n"
            "Junior Network Engineer\n"
            "dilshan@example.com | +61 400 123 456\n\n"
            "Experience\n"
            "Supported Windows and Cisco networks."
        )
        extracted = extract_resume_text("resume.txt", text.encode("utf-8"))
        details = extract_resume_details(extracted)
        self.assertIn("Dilshan Perera", extracted)
        self.assertEqual(details["candidate_name"], "Dilshan Perera")
        self.assertEqual(details["email"], "dilshan@example.com")
        self.assertTrue(details["phone"])
        self.assertIn("experience", details["sections"])

    def test_job_fit_summary_is_consistent_for_tables_and_dashboard(self):
        jobs = pd.DataFrame([{"id": 7}])
        skill_rows = pd.DataFrame(
            [
                {"job_id": 7, "raw_skill": "Cisco routing", "specific_skill": "Cisco routing", "skill_basket": "Cisco Routing & Switching"},
                {"job_id": 7, "raw_skill": "Linux", "specific_skill": "Linux", "skill_basket": "Linux & Server Support"},
            ]
        )
        profiles = pd.DataFrame(
            [{"profile_name": "Network resume", "is_active": 1, "skills_json": '[{"skill": "Cisco Routing"}]'}]
        )
        summary = build_job_fit_summary(jobs, skill_rows, profiles)
        self.assertEqual(int(summary.iloc[0]["fit_score"]), 50)
        self.assertEqual(summary.iloc[0]["fit_status"], "Partial match")

    def test_skill_and_certification_demand_is_canonical_and_job_level(self):
        skill_rows = pd.DataFrame(
            [
                {"job_id": 1, "raw_skill": "Office 365", "specific_skill": "Office 365", "skill_basket": "Microsoft 365 Administration", "created_at": "2026-01-01"},
                {"job_id": 1, "raw_skill": "Microsoft 365", "specific_skill": "Microsoft 365", "skill_basket": "Microsoft 365 Administration", "created_at": "2026-01-01"},
                {"job_id": 2, "raw_skill": "M365", "specific_skill": "M365", "skill_basket": "Microsoft 365 Administration", "created_at": "2026-01-02"},
            ]
        )
        skill_summary = build_skill_demand_summary(skill_rows)
        microsoft_row = skill_summary[skill_summary["Skill"] == "Microsoft 365"].iloc[0]

        self.assertEqual(int(microsoft_row["Jobs"]), 2)
        self.assertEqual(int(microsoft_row["Occurrences"]), 3)

        cert_rows = pd.DataFrame(
            [
                {"job_id": 1, "raw_certification": "A+", "certification_name": "CompTIA A+", "related_basket": "Hardware & Field Support", "requirement_level": "Preferred", "created_at": "2026-01-01"},
                {"job_id": 1, "raw_certification": "CompTIA A+", "certification_name": "CompTIA A+", "related_basket": "Service Desk & ITSM", "requirement_level": "Preferred", "created_at": "2026-01-01"},
                {"job_id": 2, "raw_certification": "A +", "certification_name": "A+", "related_basket": "Windows Endpoint Support", "requirement_level": "Required", "created_at": "2026-01-02"},
            ]
        )
        cert_summary = build_certification_summary(cert_rows)
        cert_row = cert_summary[cert_summary["Certification"] == "CompTIA A+"].iloc[0]
        self.assertEqual(int(cert_row["Jobs"]), 2)
        self.assertIn("Hardware & Field Support", cert_row["Related Areas"])
        self.assertIn("Required", cert_row["Requirement Levels"])

    def test_tailoring_prompts_require_truthful_source_based_content(self):
        job = {
            "company": "Example Networks",
            "job_title": "Junior Network Engineer",
            "domain": "Networking",
            "raw_description": "Support enterprise routing and switching operations.",
        }
        resume = "Supported Windows endpoints and documented incidents."
        resume_prompt = build_resume_tailoring_prompt(job, resume, "Suggestions")
        cover_prompt = build_cover_letter_prompt(job, resume, "professional", "approximately 250 words")
        follow_up_prompt = build_follow_up_email_prompt(
            job,
            resume,
            {"date_applied": "2026-11-03", "contact_name": "Recruiter"},
        )

        self.assertIn("do not invent", resume_prompt.lower())
        self.assertIn("do not invent", cover_prompt.lower())
        self.assertIn("do not invent", follow_up_prompt.lower())
        self.assertIn("Junior Network Engineer", resume_prompt)

    def test_recruiter_posting_preserves_full_title_and_entities(self):
        description = """
        About The Company
        Leaders IT (Professional Services division of Peoplebank) is a technology
        talent consultancy.

        About The Role
        Our client is looking for a Graduate / Junior&#x20;&#x49;nfrastructure Engineer.
        This is a role with a large telecommunications corporation.

        Culture & Benefits
        Training and mentoring are provided.
        """

        extracted = ai_helper.clean_extracted_data(
            {"company": "", "job_title": "", "domain": "Other"},
            description,
        )

        self.assertEqual(extracted["company"], "Leaders IT")
        self.assertEqual(extracted["recruiter_name"], "Leaders IT")
        self.assertEqual(extracted["parent_company"], "Peoplebank")
        self.assertEqual(extracted["end_client_industry"], "Telecommunications")
        self.assertEqual(extracted["posting_type"], "Recruiter / consultancy")
        self.assertEqual(
            extracted["job_title"],
            "Graduate / Junior Infrastructure Engineer",
        )

    def test_about_us_heading_preserves_network_role_and_skills_for_ai(self):
        description = """About the job
About Us
Symbio, part of the Aussie Broadband Group, operates carrier infrastructure.
About The Role
We are looking for a skilled Network Engineer to support data centre networks.
What You’ll Be Doing
Operate and maintain MPLS core and global WAN networks, configure equipment,
and develop Python scripts and CI/CD pipelines for network automation.
What you’ll bring
Experience with BGP, OSPF, IS-IS, Cisco IOS-XR, Linux, VXLAN/EVPN, Netmiko,
Nornir, NAPALM and NetBox is required.
"""
        cleaned = ai_helper.clean_job_description_for_ai(description)
        self.assertIn("Symbio", cleaned)
        self.assertIn("MPLS", cleaned)
        self.assertIn("NetBox", cleaned)

        class FakeProvider:
            model = "test-provider"

        with patch.object(ai_helper, "get_cached_extraction", return_value=None), \
             patch.object(ai_helper, "save_cached_extraction"), \
             patch.object(ai_helper, "OpenAIProvider", return_value=FakeProvider()), \
             patch.object(ai_helper, "ask_openai", return_value={
                 "company": "Symbio",
                 "job_title": "Network Engineer",
                 "domain": "Networking",
                 "technical_skills": ["MPLS", "BGP"],
                 "tools_platforms": ["Cisco IOS-XR", "NetBox"],
                 "responsibilities": ["Maintain data centre networks"],
             }) as ask:
            result = ai_helper.analyze_jd_with_openai(description)

        self.assertIn("MPLS", ask.call_args.args[0])
        self.assertIn("NetBox", ask.call_args.args[0])
        self.assertIn("MPLS", result["technical_skills"])

    def test_related_job_title_and_stock_exchange_do_not_pollute_extraction(self):
        description = (
            "About Us\nSymbio is listed on the Australian Stock Exchange.\n"
            "About The Role\nWe are looking for a skilled Network Engineer to maintain MPLS "
            "core networks, BGP and OSPF routing.\n"
        )
        extracted = ai_helper.clean_extracted_data(
            {"company": "Symbio", "job_title": "Senior Network Engineer", "domain": "Networking"},
            description,
        )
        self.assertEqual(extracted["job_title"], "Network Engineer")
        self.assertNotIn(
            "Exchange Online",
            [skill["specific_skill"] for skill in extracted["structured_skills"]],
        )

    def test_network_posting_keeps_explicit_tools_and_protocols(self):
        description = (
            "Maintain MPLS networks using BGP, OSPF, IS-IS, Cisco IOS-XR, Cisco Nexus, "
            "Arista, VXLAN/EVPN, Python, Netmiko, Nornir, NAPALM, NetBox and CI/CD."
        )
        extracted = ai_helper.build_keyword_fallback_structured_data(description)
        found = {skill["specific_skill"] for skill in extracted["structured_skills"]}
        self.assertTrue(
            {"IS-IS", "Cisco IOS-XR", "Cisco Nexus", "Arista Networking", "EVPN",
             "Netmiko", "Nornir", "NAPALM", "NetBox", "CI/CD"} <= found
        )

    def test_direct_employer_industry_is_not_an_end_client(self):
        extracted = ai_helper.clean_extracted_data(
            {
                "company": "Symbio",
                "posting_type": "Direct employer",
                "end_client_industry": "Telecommunications",
                "job_title": "Network Engineer",
                "domain": "Networking",
            },
            "Symbio is a telecommunications company looking for a Network Engineer.",
        )
        self.assertEqual(extracted["end_client_industry"], "")

    def test_public_job_url_extracts_structured_hints_and_readable_text(self):
        html = """
        <html>
          <head>
            <title>Junior Infrastructure Engineer | Example Telecom</title>
            <script type="application/ld+json">
              {
                "@context": "https://schema.org",
                "@type": "JobPosting",
                "title": "Graduate / Junior Infrastructure Engineer",
                "datePosted": "2026-11-10",
                "hiringOrganization": {"name": "Example Telecom"},
                "jobLocation": {"address": {"addressLocality": "Sydney", "addressCountry": "AU"}},
                "description": "Support enterprise infrastructure and networking projects."
              }
            </script>
          </head>
          <body>
            <nav>Navigation links</nav>
            <main>
              <h1>Graduate / Junior Infrastructure Engineer</h1>
              <p>Join our infrastructure team and build your career in enterprise technology.</p>
              <p>Support Cisco networks, Windows Server, Linux administration, and monitoring tools.</p>
              <p>Work collaboratively with experienced engineers on meaningful projects and ongoing training.</p>
              <p>Strong communication skills and a willingness to learn are important for this role.</p>
            </main>
            <footer>Privacy links</footer>
          </body>
        </html>
        """

        class FakeResponse:
            def __init__(self, payload):
                self.headers = Message()
                self.headers.add_header("Content-Type", "text/html; charset=utf-8")
                self.payload = payload.encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def read(self, _limit):
                return self.payload

            def geturl(self):
                return "https://example.com/jobs/infrastructure-engineer"

        with patch("Scripts.job_url.urlopen", return_value=FakeResponse(html)):
            posting = fetch_job_posting("https://example.com/jobs/infrastructure-engineer")

        self.assertEqual(posting["title_hint"], "Graduate / Junior Infrastructure Engineer")
        self.assertEqual(posting["company_hint"], "Example Telecom")
        self.assertEqual(posting["source_label"], "example.com")
        self.assertIn("Support Cisco networks", posting["text"])
        self.assertNotIn("Navigation links", posting["text"])

    def test_job_url_retries_one_transient_rate_limit(self):
        body = (
            "<html><head><title>Network Engineer</title></head><body>"
            "<div class='show-more-less-html__markup'><h2>About the role</h2><p>"
            + "Support enterprise networks, troubleshoot incidents, and maintain Cisco routing systems. " * 7
            + "</p></div></body></html>"
        )
        url = "https://www.linkedin.com/jobs/view/4488105269"
        rate_limit = HTTPError(url, 429, "Too Many Requests", Message(), None)
        with patch("Scripts.job_url._read_html_page", side_effect=[rate_limit, (body, url)]) as reader, \
                patch("Scripts.job_url.time.sleep") as pause:
            posting = fetch_job_posting(url)
        self.assertEqual(reader.call_count, 2)
        pause.assert_called_once_with(1)
        self.assertIn("Cisco routing systems", posting["text"])

    def test_linkedin_rate_limit_uses_public_description_after_retry(self):
        body = (
            "<div class='show-more-less-html__markup'><h2>About the role</h2><p>"
            + "Support enterprise networks, troubleshoot incidents, and maintain Cisco routing systems. " * 7
            + "</p></div>"
        )
        url = "https://www.linkedin.com/jobs/view/4488105269"
        rate_limit = HTTPError(url, 429, "Too Many Requests", Message(), None)
        with patch("Scripts.job_url._read_html_page", side_effect=[rate_limit, rate_limit, (body, url)]) as reader, \
                patch("Scripts.job_url.time.sleep"):
            posting = fetch_job_posting(url)
        self.assertEqual(reader.call_count, 3)
        self.assertEqual(posting["url"], url)
        self.assertIn("Cisco routing systems", posting["text"])

    def test_job_url_rejects_metadata_only_shell_pages(self):
        html = """
        <html><head><title>Network Engineer - Data Networks</title>
        <script type="application/ld+json">
        {"@type":"JobPosting","title":"Network Engineer - Data Networks",
         "hiringOrganization":{"name":"Aussie Broadband"},
         "jobLocation":{"address":{"addressLocality":"Melbourne"}}}
        </script></head>
        <body><main><h1>Network Engineer - Data Networks</h1><p>Aussie Broadband Melbourne</p></main></body></html>
        """

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            @property
            def headers(self):
                headers = Message()
                headers.add_header("Content-Type", "text/html; charset=utf-8")
                return headers

            def read(self, _limit):
                return html.encode("utf-8")

            def geturl(self):
                return "https://www.linkedin.com/jobs/view/4484410960/"

        with patch("Scripts.job_url.urlopen", return_value=FakeResponse()):
            with self.assertRaises(JobPageFetchError):
                fetch_job_posting("https://www.linkedin.com/jobs/view/4484410960/")

    def test_linkedin_reader_uses_job_description_not_page_shell(self):
        from Scripts.job_url import _parse_job_page

        shell = (
            "<html><body><main><h1>Network Engineer - Data Networks</h1><p>"
            + "Browse jobs and support your career. " * 20
            + "</p></main></body></html>"
        )
        _, _, shell_text = _parse_job_page(shell, linkedin=True)
        self.assertEqual(shell_text, "")

        description = (
            "<div class='show-more-less-html__markup'>"
            "<h2>About The Role</h2><p>Operate, monitor and maintain MPLS core and data centre networks.</p>"
            "<h2>What you'll bring</h2><p>Experience in BGP, OSPF, IS-IS, Cisco IOS-XR, "
            "Linux administration, VXLAN EVPN overlays, Python automation, Netmiko, Nornir, "
            "NAPALM and NetBox. Troubleshoot incidents, outages and complex distributed "
            "networks. Collaborate with engineering teams, document changes and support "
            "project delivery and on-call operations.</p></div>"
        )
        _, _, job_text = _parse_job_page(description, linkedin=True)
        self.assertIn("MPLS", job_text)
        self.assertIn("NetBox", job_text)

        full_page = (
            "<html><body><main><h1>Network Engineer</h1>"
            + description
            + "<section><h2>Similar jobs</h2><p>Senior Network Engineer</p>"
            + "<p>ServiceNow F5 Cisco Meraki</p></section></main></body></html>"
        )
        _, _, scoped_text = _parse_job_page(full_page, linkedin=True)
        self.assertIn("MPLS", scoped_text)
        self.assertNotIn("Senior Network Engineer", scoped_text)
        self.assertNotIn("ServiceNow", scoped_text)

    def test_document_versions_link_to_application(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "INSERT INTO applications (company, job_title, current_status) VALUES (?, ?, ?)",
            ("Example Networks", "Junior Network Engineer", "Applied"),
        )
        application_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        connection.commit()
        connection.close()

        resume_id = database.save_resume_version(
            "Junior Network Engineer Resume",
            "Resume content",
            source_type="tailored",
            target_job_id=1,
            application_id=application_id,
        )
        cover_id = database.save_cover_letter_version(
            "Example Networks Letter",
            "Cover letter content",
            job_id=1,
            application_id=application_id,
            status="Reviewed",
        )

        connection = sqlite3.connect(self.db_path)
        links = connection.execute(
            "SELECT resume_version_id, cover_letter_version_id, cover_letter_status FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        connection.close()

        self.assertEqual(links, (resume_id, cover_id, "Reviewed"))


if __name__ == "__main__":
    unittest.main()
