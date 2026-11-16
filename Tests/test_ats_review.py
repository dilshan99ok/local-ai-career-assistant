import json
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from App.app_utils import database
from Scripts.ats_review import (
    MAX_SECTIONS, SECTION_CHARS, fingerprint, parse_assessments, rank_reviews,
    review_pool, source_hash, split_sections,
)
from Scripts.job_fit import build_fit_snapshot
from Scripts.resume_import import extract_resume_report


def criterion(identifier="c1", kind="Required", text="BGP routing"):
    return {"id": identifier, "kind": kind, "criterion": text, "source": text,
            "requested_level": "", "alternatives": ""}


def assessment(identifier, status, quote=""):
    return {"criterion_id": identifier, "status": status, "reason": "Evidence in CV" if quote else "Not shown",
            "evidence": quote, "issue_type": "none", "edit_section": "Experience", "clarification": ""}


class SectionProvider:
    def __init__(self):
        self.prompts = []

    def generate_text(self, prompt, instructions=""):
        self.prompts.append(prompt)
        cv_id = int(re.search(r"CV ID: (\d+)", prompt).group(1))
        quote = "Production BGP routing on Cisco IOS-XR"
        found = quote in prompt
        return json.dumps({"cv_id": cv_id, "assessments": [assessment(
            "c1", "Demonstrated" if found else "Not shown", quote if found else "") ]})


class ATSReviewTests(unittest.TestCase):
    def test_required_evidence_outranks_higher_skill_coverage(self):
        criteria = [criterion("c1", "Required", "Production BGP routing"),
                    criterion("c2", "Preferred", "Linux")]
        weak = {"profile_id": 1, "complete": True,
                "assessments": [assessment("c1", "Not shown"), assessment("c2", "Demonstrated", "Linux") ]}
        strong = {"profile_id": 2, "complete": True,
                  "assessments": [assessment("c1", "Demonstrated", "Production BGP routing"),
                                  assessment("c2", "Not shown")]}
        # Skill coverage can favour CV 1; the evidence ranking must still choose CV 2.
        skill_coverage = {1: 80, 2: 40}
        self.assertGreater(skill_coverage[1], skill_coverage[2])
        self.assertEqual(rank_reviews([weak, strong], criteria), (2, []))

    def test_middle_of_long_cv_is_reviewed(self):
        quote = "Production BGP routing on Cisco IOS-XR"
        text = "Intro\n" + "A" * 7400 + "\n" + quote + "\n" + "B" * 7600
        sections = split_sections(text)
        self.assertGreater(len(sections), 2)
        self.assertEqual("".join(section["text"] for section in sections), text)
        self.assertTrue(any(quote in section["text"] for section in sections[1:-1]))
        profiles = pd.DataFrame([{"id": 1, "profile_name": "Network CV", "target_domain": "Networking",
                                  "resume_text": text, "skills_json": "[]", "extraction_report_json": "{}"}])
        job = {"id": 1, "job_title": "Engineer", "raw_description": "Production BGP routing"}
        provider = SectionProvider()
        result = review_pool(job, profiles, pd.DataFrame([{"profile_id": 1, "matched": 0}]),
                             {"version": 1, "criteria": [criterion("c1", text="Production BGP routing")]}, provider)
        self.assertEqual(len(provider.prompts), len(sections))
        self.assertEqual(result["selected_profile_id"], 1)
        self.assertEqual(result["cv_reviews"][0]["assessments"][0]["evidence"], quote)
        self.assertFalse(result["provisional"])

    def test_oversized_cv_is_flagged_and_not_ranked(self):
        text = "A" * (SECTION_CHARS * (MAX_SECTIONS + 1))
        profiles = pd.DataFrame([{"id": 1, "profile_name": "Long CV", "resume_text": text,
                                  "skills_json": "[]", "extraction_report_json": "{}"}])
        provider = SectionProvider()
        result = review_pool({"job_title": "Engineer", "raw_description": "BGP routing"}, profiles,
                             pd.DataFrame([{"profile_id": 1, "matched": 0}]),
                             {"version": 1, "criteria": [criterion()]}, provider)
        self.assertTrue(result["provisional"])
        self.assertIsNone(result["selected_profile_id"])
        self.assertTrue(result["cv_reviews"][0]["omitted_sections"])
        self.assertEqual(result["cv_reviews"][0]["assessments"][0]["status"], "Unable to assess")

    def test_invented_quote_and_wrong_ids_are_rejected(self):
        rows = [criterion()]
        with self.assertRaisesRegex(ValueError, "unsupported CV quote"):
            parse_assessments(json.dumps({"cv_id": 1, "assessments": [assessment(
                "c1", "Demonstrated", "Invented production work")]}), rows, "Only a lab project", 1)
        with self.assertRaisesRegex(ValueError, "unknown CV ID"):
            parse_assessments(json.dumps({"cv_id": 99, "assessments": [assessment(
                "c1", "Not shown")]}), rows, "Only a lab project", 1)
        with self.assertRaisesRegex(ValueError, "unknown criterion ID"):
            parse_assessments(json.dumps({"cv_id": 1, "assessments": [assessment(
                "c99", "Not shown")]}), rows, "Only a lab project", 1)

    def test_lab_exposure_does_not_satisfy_production_level(self):
        required = criterion(text="Cisco administration")
        required["requested_level"] = "Production environment"
        rows = parse_assessments(json.dumps({"cv_id": 1, "assessments": [assessment(
            "c1", "Demonstrated", "Cisco home lab")]}), [required], "Cisco home lab", 1)
        self.assertEqual(rows[0]["status"], "Partially demonstrated")

    def test_saving_edited_checklist_invalidates_cached_review(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            job = {"id": 7, "raw_description": "BGP routing and Linux administration"}
            rows = [criterion()]
            version = database.save_job_cv_checklist(7, source_hash(job), rows)
            profiles = pd.DataFrame([{"id": 1, "resume_text": "BGP", "skills_json": "[]"}])
            saved = database.get_job_cv_checklist(7)
            key = fingerprint(job, profiles, saved)
            result = {"schema_version": "ats-preview-v1", "selected_profile_id": 1,
                      "cv_reviews": [{"profile_id": 1}]}
            database.save_job_resume_recommendation(7, key, result)
            self.assertEqual(database.get_job_resume_recommendation(7, key), result)
            rows[0]["requested_level"] = "Production"
            self.assertEqual(database.save_job_cv_checklist(7, source_hash(job), rows), version + 1)
            self.assertIsNone(database.get_job_resume_recommendation(7, key))
            self.assertNotEqual(key, fingerprint(job, profiles, database.get_job_cv_checklist(7)))

    def test_blank_pdf_page_is_an_extraction_issue(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        content = io.BytesIO()
        writer.write(content)
        report = extract_resume_report("cv.pdf", content.getvalue())
        self.assertIn("page(s): 1", report["issues"][0])
        self.assertNotIn("omitted_sections", report)

    def test_legacy_pdf_extraction_report_is_backfilled(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        content = io.BytesIO()
        writer.write(content)
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            database.save_resume_profile("Old PDF", "Saved text", [], source_filename="old.pdf",
                                         source_type="PDF", source_file=content.getvalue())
            database.ensure_resume_extraction_reports()
            profile = database.get_resume_profiles_df().iloc[0]
            self.assertIn("page(s): 1", json.loads(profile["extraction_report_json"])["issues"][0])


if __name__ == "__main__":
    unittest.main()
