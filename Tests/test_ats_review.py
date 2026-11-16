import json
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from App.app_utils import database
from Scripts.ats_review import (
    MAX_SECTIONS, SCHEMA, SECTION_CHARS, UNVERIFIED_SOURCE, checklist_guidance_hash,
    fingerprint, generate_checklist, parse_assessments, rank_reviews,
    request_assessments, required_criteria_summary, review_pool, source_hash, split_sections,
)
from Scripts.job_fit import build_fit_snapshot
from Scripts.resume_import import extract_resume_report
from Scripts.tailoring import (
    build_resume_tailoring_prompt, build_screening_context,
    format_screening_suggestions, generate_resume_tailoring,
)


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
    def test_checklist_keeps_separate_items_with_shared_source(self):
        job = {"raw_description": "Experience with PC equipment, Azure AD, Office 365 and Adobe products is beneficial."}
        rows = [
            {"kind": "Preferred", "criterion": item, "source": job["raw_description"],
             "requested_level": "", "alternatives": ""}
            for item in ("PC equipment", "Azure AD", "Office 365", "Adobe products")
        ]
        provider = Mock()
        provider.generate_text.return_value = json.dumps({"criteria": rows})
        checklist = generate_checklist(job, provider)
        self.assertEqual(len(checklist), 4)
        self.assertTrue(all(row["kind"] == "Preferred" for row in checklist))
        self.assertIn("Split separately assessable", provider.generate_text.call_args.args[0])

    def test_duration_is_reconciled_across_sections_and_validated(self):
        dates = "IT support analyst, January 2022 - December 2023"
        duties = "Resolved help desk tickets for staff"
        cv_text = dates + "\n" + "X" * 7100 + "\n" + duties
        row = criterion(text="At least one year in an IT support role")
        provider = Mock()
        def respond(prompt, instructions=""):
            if "VALIDATED SECTION EVIDENCE:" in prompt:
                self.assertIn(dates, prompt)
                self.assertIn(duties, prompt)
                return json.dumps({"cv_id": 1, "assessments": [assessment("c1", "Demonstrated", duties)]})
            quote = dates if dates in prompt.split("CV SECTION", 1)[-1] else duties
            return json.dumps({"cv_id": 1, "assessments": [assessment("c1", "Partially demonstrated", quote)]})
        provider.generate_text.side_effect = respond
        profiles = pd.DataFrame([{"id": 1, "profile_name": "Support CV", "resume_text": cv_text,
                                  "extraction_report_json": "{}"}])
        result = review_pool({"job_title": "Support", "raw_description": row["source"]}, profiles,
                             pd.DataFrame([{"profile_id": 1, "matched": 0}]),
                             {"version": 1, "criteria": [row]}, provider)
        self.assertEqual(result["cv_reviews"][0]["assessments"][0]["status"], "Demonstrated")
        self.assertEqual(provider.generate_text.call_count, len(split_sections(cv_text)) + 1)

    def test_guidance_changes_invalidate_review_fingerprint(self):
        job = {"id": 3, "raw_description": "BGP"}
        profiles = pd.DataFrame([{"id": 1, "resume_text": "BGP"}])
        before = fingerprint(job, profiles, {"version": 1, "criteria": [criterion()]})
        from Scripts import ats_review
        original = ats_review.load_prompt
        with patch.object(ats_review, "load_prompt", side_effect=lambda name: original(name) + " updated" if name == "cv-evidence-review" else original(name)):
            after = fingerprint(job, profiles, {"version": 1, "criteria": [criterion()]})
        self.assertNotEqual(before, after)

    def test_legacy_checklist_guidance_is_identified(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            database.save_job_cv_checklist(3, "source", [criterion()])
            self.assertEqual(database.get_job_cv_checklist(3)["guidance_hash"], "")
            database.save_job_cv_checklist(3, "source", [criterion()], checklist_guidance_hash())
            self.assertEqual(database.get_job_cv_checklist(3)["guidance_hash"], checklist_guidance_hash())

    def test_saved_screening_follows_selected_cv_into_tailoring(self):
        criteria = [criterion("c1", text="Production BGP routing"),
                    criterion("c2", "Preferred", "Linux administration")]
        checklist = {"version": 4, "criteria": criteria}
        weaker = {"profile_id": 1, "complete": True,
                  "assessments": [assessment("c1", "Not shown"),
                                  assessment("c2", "Demonstrated", "Linux") ]}
        stronger = {"profile_id": 2, "complete": True,
                    "assessments": [assessment("c1", "Partially demonstrated", "BGP lab"),
                                    assessment("c2", "Not shown")]}
        recommendation = {"checklist_version": 4, "selected_profile_id": None,
                          "tied_profile_ids": [1, 2], "provisional": False,
                          "cv_reviews": [weaker, stronger]}
        context = build_screening_context(checklist, recommendation, 2)
        self.assertEqual(context["profile_id"], 2)
        self.assertEqual(context["criteria"][0]["status"], "Partially demonstrated")
        self.assertEqual(context["edits"][0]["criterion"], "Production BGP routing")
        suggestions = format_screening_suggestions(context)
        self.assertIn("Production BGP routing", suggestions)
        self.assertIn("Where: Experience", suggestions)
        self.assertIn("BGP lab", suggestions)
        self.assertNotIn("Other checklist findings", suggestions)
        prompt = build_resume_tailoring_prompt(
            {"job_title": "Network engineer", "raw_description": "Production BGP routing"},
            "BGP lab", "Tailored draft", context)
        self.assertIn('"status": "Partially demonstrated"', prompt)
        self.assertIn("instead of repeating the screening analysis", prompt)
        with patch("Scripts.tailoring.OpenAIProvider") as provider_class:
            provider = Mock()
            provider.generate_text.return_value = "draft"
            provider_class.return_value = provider
            self.assertEqual(generate_resume_tailoring(
                {"job_title": "Network engineer", "raw_description": "Production BGP routing"},
                "BGP lab", "Tailored draft", context), "draft")
            provider.generate_text.assert_called_once()

    def test_stale_or_incomplete_screening_is_not_forwarded(self):
        rows = [criterion()]
        checklist = {"version": 2, "criteria": rows}
        review = {"profile_id": 1, "complete": False,
                  "assessments": [assessment("c1", "Unable to assess")]}
        saved = {"checklist_version": 2, "cv_reviews": [review]}
        self.assertIsNone(build_screening_context(checklist, saved, 1))
        review["complete"] = True
        self.assertIsNone(build_screening_context(checklist, saved, 2))
        saved["checklist_version"] = 1
        self.assertIsNone(build_screening_context(checklist, saved, 1))
        saved["checklist_version"] = 2
        review["assessments"] = [assessment("unexpected", "Demonstrated", "BGP")]
        self.assertIsNone(build_screening_context(checklist, saved, 1))

    def test_change_plan_includes_demonstrated_evidence_as_strength(self):
        criteria = [criterion("required", text="Production routing"),
                    criterion("preferred", "Preferred", "Linux")]
        review = {"profile_id": 3, "complete": True,
                  "assessments": [assessment("required", "Partially demonstrated", "Routing lab"),
                                  assessment("preferred", "Demonstrated", "Linux server support")]}
        context = build_screening_context(
            {"version": 1, "criteria": criteria},
            {"checklist_version": 1, "cv_reviews": [review]}, 3)
        plan = format_screening_suggestions(context)
        self.assertIn("## Clarify or improve", plan)
        self.assertIn("Routing lab", plan)
        self.assertIn("Confirm first", plan)
        self.assertIn("## Evidence to bring forward", plan)
        self.assertIn("Linux server support", plan)

    def test_required_criteria_percentage_excludes_partial_and_preferred(self):
        criteria = [criterion("c1", text="BGP"), criterion("c2", text="OSPF"),
                    criterion("c3", text="Linux"), criterion("c4", "Preferred", "Python")]
        review = {"assessments": [assessment("c1", "Demonstrated", "BGP"),
                                  assessment("c2", "Partially demonstrated", "OSPF lab"),
                                  assessment("c3", "Not shown"),
                                  assessment("c4", "Demonstrated", "Python")]}
        summary = required_criteria_summary(review, criteria)
        self.assertEqual((summary["demonstrated"], summary["total"], summary["percentage"]), (1, 3, 33))
        self.assertEqual(summary["partial"], ["OSPF"])
        self.assertEqual(summary["missing"], ["Linux"])

    def test_required_criteria_unable_and_none_specified(self):
        review = {"assessments": [assessment("c1", "Demonstrated", "BGP"),
                                  assessment("c2", "Unable to assess")]}
        summary = required_criteria_summary(review, [criterion("c1"), criterion("c2", text="Linux")])
        self.assertEqual(summary["unable"], ["Linux"])
        self.assertEqual((summary["demonstrated"], summary["total"]), (1, 2))
        self.assertIsNone(required_criteria_summary(review, [criterion("c3", "Preferred")])["percentage"])

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
        with self.assertRaisesRegex(ValueError, "unknown criterion ID"):
            parse_assessments(json.dumps({"cv_id": 1, "assessments": [
                assessment("c1", "Not shown"), assessment("c1", "Not shown")]}),
                [criterion("c1"), criterion("c2")], "Only a lab project", 1)

    def test_unverifiable_quote_is_retried_with_exact_cv_evidence(self):
        provider = Mock()
        provider.generate_text.side_effect = [
            json.dumps({"cv_id": 1, "assessments": [assessment("c1", "Demonstrated", "Invented quote")]}),
            json.dumps({"cv_id": 1, "assessments": [assessment("c1", "Demonstrated", "BGP lab project")]}),
        ]
        rows, affected = request_assessments(provider, "CV ID: 1", [criterion()], "BGP lab project", 1)
        self.assertEqual(provider.generate_text.call_count, 2)
        self.assertEqual(rows[0]["evidence"], "BGP lab project")
        self.assertEqual(affected, [])

    def test_repeated_unverifiable_quote_marks_only_affected_cv_incomplete(self):
        provider = Mock()
        def respond(prompt, instructions=""):
            cv_id = int(re.search(r"CV ID: (\d+)", prompt).group(1))
            quote = "Invented quote" if cv_id == 1 else "BGP lab project"
            return json.dumps({"cv_id": cv_id, "assessments": [assessment("c1", "Demonstrated", quote)]})
        provider.generate_text.side_effect = respond
        profiles = pd.DataFrame([
            {"id": 1, "profile_name": "Bad quote", "resume_text": "BGP lab project", "extraction_report_json": "{}"},
            {"id": 2, "profile_name": "Good quote", "resume_text": "BGP lab project", "extraction_report_json": "{}"},
        ])
        result = review_pool({"job_title": "Engineer", "raw_description": "BGP routing"}, profiles,
                             pd.DataFrame([{"profile_id": 1, "matched": 1}, {"profile_id": 2, "matched": 1}]),
                             {"version": 1, "criteria": [criterion()]}, provider)
        self.assertEqual(result["selected_profile_id"], 2)
        self.assertTrue(result["provisional"])
        bad = result["cv_reviews"][0]
        self.assertFalse(bad["complete"])
        self.assertEqual(bad["assessments"][0]["status"], "Unable to assess")
        self.assertEqual(bad["assessments"][0]["evidence"], "")
        self.assertIn("c1", bad["validation_issues"][0])

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
            result = {"schema_version": SCHEMA, "selected_profile_id": 1,
                      "cv_reviews": [{"profile_id": 1}]}
            database.save_job_resume_recommendation(7, key, result)
            self.assertEqual(database.get_job_resume_recommendation(7, key), result)
            rows[0]["requested_level"] = "Production"
            self.assertEqual(database.save_job_cv_checklist(7, source_hash(job), rows), version + 1)
            self.assertIsNone(database.get_job_resume_recommendation(7, key))
            self.assertNotEqual(key, fingerprint(job, profiles, database.get_job_cv_checklist(7)))

    def test_saving_unchanged_checklist_keeps_cached_review(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            job = {"id": 7, "raw_description": "BGP routing and Linux administration"}
            rows = [criterion()]
            version = database.save_job_cv_checklist(7, source_hash(job), rows, "original guidance")
            saved = database.get_job_cv_checklist(7)
            profiles = pd.DataFrame([{"id": 1, "resume_text": "BGP", "skills_json": "[]"}])
            key = fingerprint(job, profiles, saved)
            result = {"schema_version": SCHEMA, "selected_profile_id": 1,
                      "cv_reviews": [{"profile_id": 1}]}
            database.save_job_resume_recommendation(7, key, result)
            self.assertEqual(database.save_job_cv_checklist(7, source_hash(job), rows, "new guidance"), version)
            updated = database.get_job_cv_checklist(7)
            self.assertEqual(updated["criteria"], saved["criteria"])
            self.assertEqual(updated["version"], saved["version"])
            self.assertEqual(updated["guidance_hash"], "new guidance")
            self.assertEqual(fingerprint(job, profiles, updated), key)
            self.assertEqual(database.get_job_resume_recommendation(7, key), result)

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

    def test_missing_original_is_a_warning_and_saved_text_can_be_ranked(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            profile_id = database.save_resume_profile(
                "Legacy CV", "Production BGP routing on Cisco IOS-XR", [],
                source_filename="old.pdf", source_type="PDF")
            database.ensure_resume_extraction_reports()
            profile = database.get_resume_profiles_df().iloc[0]
            report = json.loads(profile["extraction_report_json"])
            self.assertEqual(report["issues"], [])
            self.assertEqual(report["warnings"], [UNVERIFIED_SOURCE])
            job = {"job_title": "Engineer", "raw_description": "Production BGP routing"}
            result = review_pool(job, database.get_resume_profiles_df(),
                                 pd.DataFrame([{"profile_id": profile_id, "matched": 1}]),
                                 {"version": 1, "criteria": [criterion(text="Production BGP routing")]},
                                 SectionProvider())
            self.assertEqual(result["selected_profile_id"], profile_id)
            self.assertFalse(result["provisional"])
            self.assertEqual(result["cv_reviews"][0]["extraction_warnings"], [UNVERIFIED_SOURCE])

    def test_confirmed_extraction_loss_still_blocks_full_review(self):
        profiles = pd.DataFrame([{"id": 1, "profile_name": "Partial PDF",
                                  "resume_text": "Production BGP routing on Cisco IOS-XR",
                                  "extraction_report_json": json.dumps({"issues": ["No readable text on PDF page(s): 2"]})}])
        result = review_pool({"job_title": "Engineer", "raw_description": "Production BGP routing"},
                             profiles, pd.DataFrame([{"profile_id": 1, "matched": 1}]),
                             {"version": 1, "criteria": [criterion(text="Production BGP routing")]},
                             SectionProvider())
        self.assertTrue(result["provisional"])
        self.assertIsNone(result["selected_profile_id"])
        self.assertIn("page(s): 2", result["cv_reviews"][0]["extraction_issues"][0])

    def test_legacy_source_warning_moves_out_of_extraction_issues(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            profile_id = database.save_resume_profile("Legacy CV", "Saved CV text", [],
                                                      source_filename="old.pdf", source_type="PDF",
                                                      extraction_report={"issues": [UNVERIFIED_SOURCE]})
            database.ensure_resume_extraction_reports()
            report = json.loads(database.get_resume_profiles_df().iloc[0]["extraction_report_json"])
            self.assertEqual(report["issues"], [])
            self.assertEqual(report["warnings"], [UNVERIFIED_SOURCE])

    def test_previous_review_schema_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(database, "DB_PATH", Path(directory) / "career.db"):
            database.initialize_database()
            old = {"schema_version": "ats-preview-v1", "selected_profile_id": 1, "cv_reviews": []}
            database.save_job_resume_recommendation(9, "old-key", old)
            self.assertIsNone(database.get_job_resume_recommendation(9, "old-key"))


if __name__ == "__main__":
    unittest.main()
