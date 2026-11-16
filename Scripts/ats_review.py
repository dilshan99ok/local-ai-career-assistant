"""Evidence based preview of what a saved job ad and CV pool show at screening."""

import hashlib
import json
import re

from Scripts.ai_provider import OpenAIProvider, configured_model
from Scripts.prompt_loader import load_prompt, render_prompt


SCHEMA = "ats-preview-v4"
RULES = 4
SECTION_CHARS = 7000
MAX_SECTIONS = 16
STATUSES = {"Demonstrated", "Partially demonstrated", "Not shown", "Unable to assess"}
KINDS = {"Required", "Preferred", "Screening"}
ISSUES = {"none", "unclear wording", "missing CV evidence", "unmet requirement"}
UNVERIFIED_SOURCE = "Original file unavailable; extraction cannot be checked."


def parse_json(raw):
    value = str(raw or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("AI returned unreadable screening data.") from error
    if not isinstance(result, dict):
        raise ValueError("AI returned invalid screening data.")
    return result


def fold(value):
    return " ".join(str(value or "").split()).casefold()


def source_hash(job):
    return hashlib.sha256(str(job.get("raw_description") or "").encode("utf-8")).hexdigest()


def guidance_hash(*names):
    content = "\n".join(load_prompt(name) for name in names)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def checklist_guidance_hash():
    return guidance_hash("job-checklist", "json-output-system")


def split_sections(text, limit=SECTION_CHARS):
    """Exact contiguous slices; no middle content is discarded silently."""
    text = str(text or "")
    sections, start = [], 0
    while start < len(text):
        end = min(start + limit, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + limit // 2, end)
            if boundary >= 0:
                end = boundary + 1
        part = text[start:end]
        label = next((line.strip() for line in part.splitlines() if line.strip()), "")
        sections.append({"id": f"s{len(sections)+1}", "start": start, "end": end,
                         "label": label[:65] or f"Section {len(sections)+1}", "text": part})
        start = end
    return sections


def validate_checklist(rows, job_text):
    if not isinstance(rows, list):
        raise ValueError("The job checklist must be a list.")
    cleaned, seen, next_id = [], set(), 1
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid checklist row.")
        kind = str(row.get("kind") or "").strip().title()
        criterion = str(row.get("criterion") or "").strip()
        source = str(row.get("source") or "").strip()
        if kind not in KINDS or not criterion or not source:
            raise ValueError("Each checklist row needs a type, criterion, and source wording.")
        if fold(source) not in fold(job_text):
            raise ValueError(f"Source wording for '{criterion}' was not found in the job description.")
        identifier = str(row.get("id") or "").strip()
        if identifier.lower() in {"nan", "none"}:
            identifier = ""
        if not identifier:
            while f"c{next_id}" in seen:
                next_id += 1
            identifier = f"c{next_id}"
            next_id += 1
        if identifier in seen:
            raise ValueError(f"Duplicate checklist ID: {identifier}")
        seen.add(identifier)
        cleaned.append({"id": identifier, "kind": kind, "criterion": criterion,
                        "source": source,
                        "requested_level": str(row.get("requested_level") or "").strip(),
                        "alternatives": str(row.get("alternatives") or "").strip()})
    return cleaned


def generate_checklist(job, provider=None):
    description = str(job.get("raw_description") or "")
    if not description.strip():
        raise ValueError("This job has no saved description to screen against.")
    sections = split_sections(description)
    if len(sections) > MAX_SECTIONS:
        raise ValueError("The job description is too long to review completely. Shorten it before building a checklist.")
    provider = provider or OpenAIProvider()
    rows = []
    for section in sections:
        prompt = render_prompt("job-checklist", SECTION_ID=section["id"], SECTION_TEXT=section["text"])
        result = parse_json(provider.generate_text(prompt, instructions=load_prompt("json-output-system")))
        candidates = result.get("criteria")
        if not isinstance(candidates, list):
            raise ValueError("AI did not return a usable job checklist.")
        for row in candidates:
            if not isinstance(row, dict) or not fold(row.get("source")) or fold(row.get("source")) not in fold(section["text"]):
                raise ValueError("AI supplied checklist wording outside the reviewed job section.")
            rows.append(row)
    unique, seen = [], set()
    for row in rows:
        key = (fold(row.get("source")), fold(row.get("criterion")))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return validate_checklist(unique, description)


def extraction_report(profile):
    try:
        report = json.loads(profile.get("extraction_report_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        report = {}
    return report if isinstance(report, dict) else {}


def extraction_issues(profile):
    issues = extraction_report(profile).get("issues", [])
    issues = [str(value) for value in issues if str(value).strip() and str(value) != UNVERIFIED_SOURCE] if isinstance(issues, list) else []
    if not str(profile.get("resume_text") or "").strip():
        issues.append("No readable CV text is saved.")
    return issues


def extraction_warnings(profile):
    report = extraction_report(profile)
    warnings = report.get("warnings", [])
    warnings = [str(value) for value in warnings if str(value).strip()] if isinstance(warnings, list) else []
    issues = report.get("issues", [])
    if isinstance(issues, list) and UNVERIFIED_SOURCE in issues and UNVERIFIED_SOURCE not in warnings:
        warnings.append(UNVERIFIED_SOURCE)
    return warnings


def fingerprint(job, profiles_df, checklist=None, rankings=None, include_checklist_metadata=False):
    payload = {
        "schema": SCHEMA, "rules": RULES, "model": configured_model(),
        "review_guidance": guidance_hash("cv-evidence-review", "cv-evidence-system", "cv-duration-merge"),
        "checklist_guidance": checklist_guidance_hash(),
        "job": {key: job.get(key) for key in ("id", "company", "job_title", "domain", "raw_description")},
        # Presentation/migration metadata does not alter the reviewed criteria.
        "checklist": (checklist or {}) if include_checklist_metadata else
                     {key: (checklist or {}).get(key) for key in ("source_hash", "version", "criteria")},
        "profiles": [{key: row.get(key) for key in (
            "id", "profile_name", "target_domain", "resume_text", "skills_json",
            "extraction_report_json", "source_filename", "source_type", "updated_at")}
            for _, row in profiles_df.iterrows()],
        "rankings": rankings.to_dict("records") if rankings is not None else [],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def assessment_prompt(job, criteria, profile, section, overlap):
    return render_prompt(
        "cv-evidence-review", JOB_TITLE=job.get("job_title", ""),
        CHECKLIST_JSON=json.dumps(criteria, ensure_ascii=False), CV_ID=int(profile["id"]),
        SKILL_OVERLAP=overlap, SECTION_ID=section["id"],
        SECTION_LABEL=section["label"], SECTION_TEXT=section["text"],
    )


def parse_assessments(raw, criteria, section_text, cv_id):
    result = parse_json(raw)
    if result.get("cv_id") != cv_id:
        raise ValueError("AI returned an unknown CV ID.")
    rows = result.get("assessments")
    expected = {item["id"] for item in criteria}
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("AI did not assess every criterion for a CV section.")
    parsed, seen = [], set()
    criteria_by_id = {item["id"]: item for item in criteria}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("AI returned an invalid criterion assessment.")
        identifier = str(row.get("criterion_id") or "")
        status = str(row.get("status") or "")
        quote = str(row.get("evidence") or "").strip()
        if identifier not in expected or identifier in seen or status not in STATUSES:
            raise ValueError("AI returned an unknown criterion ID or status.")
        if quote and fold(quote) not in fold(section_text):
            raise ValueError(f"AI supplied an unsupported CV quote for {identifier}.")
        if status in {"Demonstrated", "Partially demonstrated"} and not quote:
            raise ValueError(f"AI supplied no CV quote for {identifier}.")
        issue = str(row.get("issue_type") or "none").strip().lower()
        issue = issue if issue in ISSUES else "none"
        if issue == "unmet requirement" and not quote:
            raise ValueError(f"AI supplied no evidence for unmet requirement {identifier}.")
        level = fold(criteria_by_id[identifier]["requested_level"] + " " + criteria_by_id[identifier]["criterion"])
        downgraded = (status == "Demonstrated"
                      and any(term in level for term in ("production", "commercial", "enterprise"))
                      and re.search(r"\b(home\s*lab|lab|coursework|personal project)\b", quote, re.I)
                      and not re.search(r"\b(production|commercial|enterprise|employer|at work)\b", quote, re.I))
        if downgraded:
            status = "Partially demonstrated"
            issue = "unclear wording"
        seen.add(identifier)
        parsed.append({"criterion_id": identifier, "status": status,
                       "reason": ("Lab or project evidence does not establish the requested level."
                                  if downgraded else str(row.get("reason") or "").strip()),
                       "evidence": quote,
                       "issue_type": issue,
                       "edit_section": str(row.get("edit_section") or "").strip(),
                       "clarification": str(row.get("clarification") or "").strip()})
    return parsed


def recover_unverified_quotes(raw, criteria, source_text, cv_id):
    """Discard unverifiable evidence while preserving valid criterion results."""
    result = parse_json(raw)
    rows = result.get("assessments")
    expected = {item["id"] for item in criteria}
    if result.get("cv_id") != cv_id or not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("AI returned an invalid CV assessment structure.")
    seen, affected = set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("AI returned an invalid criterion assessment.")
        identifier = str(row.get("criterion_id") or "")
        status = str(row.get("status") or "")
        if identifier not in expected or identifier in seen or status not in STATUSES:
            raise ValueError("AI returned an unknown criterion ID or status.")
        seen.add(identifier)
        quote = str(row.get("evidence") or "").strip()
        unverified = bool(quote and fold(quote) not in fold(source_text))
        missing = status in {"Demonstrated", "Partially demonstrated"} and not quote
        unmet_without_quote = row.get("issue_type") == "unmet requirement" and not quote
        if unverified or missing or unmet_without_quote:
            affected.append(identifier)
            row.update(status="Unable to assess", reason="The AI's CV evidence could not be verified.",
                       evidence="", issue_type="missing CV evidence", edit_section="", clarification="")
    parsed = parse_assessments(json.dumps(result), criteria, source_text, cv_id)
    return parsed, affected


def request_assessments(provider, prompt, criteria, source_text, cv_id):
    """Retry one invalid response, then quarantine unsupported quotes."""
    instructions = load_prompt("cv-evidence-system")
    raw = provider.generate_text(prompt, instructions=instructions)
    try:
        return parse_assessments(raw, criteria, source_text, cv_id), []
    except ValueError as first_error:
        correction = ("\n\nYour previous JSON failed validation: " + str(first_error)
                      + " Return the complete JSON again. Copy each evidence excerpt exactly "
                        "from the supplied CV text. If you cannot verify an excerpt, mark that "
                        "criterion Unable to assess and leave evidence empty. Do not invent quotes.")
        raw = provider.generate_text(prompt + correction, instructions=instructions)
        try:
            return parse_assessments(raw, criteria, source_text, cv_id), []
        except ValueError as retry_error:
            if not any(message in str(retry_error) for message in (
                    "unsupported CV quote", "no CV quote", "no evidence for unmet requirement")):
                raise
            parsed, affected = recover_unverified_quotes(raw, criteria, source_text, cv_id)
            if not affected:
                raise
            return parsed, affected


def combine_assessments(criteria, section_answers, incomplete):
    priority = {"Demonstrated": 3, "Partially demonstrated": 2, "Not shown": 1, "Unable to assess": 0}
    combined = []
    for criterion in criteria:
        options = [row for group in section_answers for row in group if row["criterion_id"] == criterion["id"]]
        best = max(options, key=lambda row: priority[row["status"]]).copy() if options else {
            "criterion_id": criterion["id"], "status": "Unable to assess",
            "reason": "No readable section was reviewed.", "evidence": "", "issue_type": "missing CV evidence",
            "edit_section": "", "clarification": ""}
        if best["status"] == "Not shown" and any(row["status"] == "Unable to assess" for row in options):
            best.update(status="Unable to assess", reason="One reviewed section could not be assessed.")
        if incomplete and best["status"] in {"Not shown", "Unable to assess"}:
            best.update(status="Unable to assess", reason="Part of this CV was not reviewable.", issue_type="missing CV evidence")
        combined.append(best)
    return combined


def duration_criteria(criteria):
    """Find explicit experience durations that need evidence across sections."""
    return [item for item in criteria if re.search(
        r"\b(?:\d+(?:\.\d+)?\s*\+?|one|two|three|four|five)\s*(?:years?|yrs?|months?)\b",
        f"{item['criterion']} {item['requested_level']}", re.I)]


def reconcile_duration(job, profile, criteria, section_answers, combined, provider):
    """Reassess duration only after evidence from all CV sections is available."""
    duration = duration_criteria(criteria)
    if not duration or len(section_answers) < 2:
        return combined, []
    evidence = [
        {"section": index + 1, "assessments": [row for row in rows
          if row["criterion_id"] in {item["id"] for item in duration}]}
        for index, rows in enumerate(section_answers)
    ]
    lines = str(profile.get("resume_text") or "").splitlines()
    date_line = re.compile(r"\b(?:20\d{2}|19\d{2}|present|current)\b", re.I)
    chronology = "\n".join(
        f"Line {index + 1}: {lines[index]}" for index in range(len(lines))
        if any(date_line.search(lines[near]) for near in range(max(0, index - 2), min(len(lines), index + 3)))
    )
    prompt = render_prompt(
        "cv-duration-merge", JOB_TITLE=job.get("job_title", ""),
        CHECKLIST_JSON=json.dumps(duration, ensure_ascii=False),
        CV_ID=int(profile["id"]), SECTION_EVIDENCE=json.dumps(evidence, ensure_ascii=False),
        CHRONOLOGY=chronology,
    )
    merged, affected = request_assessments(
        provider, prompt, duration, str(profile.get("resume_text") or ""), int(profile["id"]))
    by_id = {row["criterion_id"]: row for row in merged}
    return [by_id.get(row["criterion_id"], row) for row in combined], affected


def evidence_score(review, criteria, kind):
    by_id = {row["criterion_id"]: row["status"] for row in review["assessments"]}
    values = [by_id[item["id"]] for item in criteria if item["kind"] == kind]
    return (2 * values.count("Demonstrated") + values.count("Partially demonstrated"),
            values.count("Demonstrated"))


def required_criteria_summary(review, criteria):
    """Report demonstrated requirements without changing the evidence ranking."""
    required = [item for item in criteria if item["kind"] == "Required"]
    assessments = {item["criterion_id"]: item["status"] for item in review["assessments"]}
    groups = {status: [] for status in STATUSES}
    for item in required:
        status = assessments.get(item["id"], "Unable to assess")
        groups[status].append(item["criterion"])
    demonstrated = len(groups["Demonstrated"])
    total = len(required)
    return {
        "demonstrated": demonstrated,
        "total": total,
        "percentage": round(demonstrated / total * 100) if total else None,
        "partial": groups["Partially demonstrated"],
        "missing": groups["Not shown"],
        "unable": groups["Unable to assess"],
    }


def rank_reviews(reviews, criteria):
    eligible = [review for review in reviews if review["complete"]]
    if not eligible:
        return None, []
    key = lambda review: (evidence_score(review, criteria, "Required"),
                          evidence_score(review, criteria, "Preferred"))
    top = max(key(review) for review in eligible)
    ties = [review["profile_id"] for review in eligible if key(review) == top]
    return (ties[0], []) if len(ties) == 1 else (None, ties)


def build_edits(review, criteria):
    if not review:
        return []
    by_id = {row["criterion_id"]: row for row in review["assessments"]}
    ordered = [item for kind in ("Required", "Preferred") for item in criteria if item["kind"] == kind]
    ordered.sort(key=lambda item: (item["kind"] != "Required",
                                   by_id[item["id"]]["status"] != "Partially demonstrated"))
    edits = []
    for criterion in ordered:
        assessment = by_id[criterion["id"]]
        if assessment["status"] == "Demonstrated":
            continue
        issue = assessment["issue_type"]
        if issue == "none":
            issue = "unclear wording" if assessment["status"] == "Partially demonstrated" else "missing CV evidence"
        quote = assessment["evidence"]
        edits.append({"criterion_id": criterion["id"], "criterion": criterion["criterion"],
                      "kind": criterion["kind"], "issue_type": issue,
                      "edit_section": assessment["edit_section"] or "Relevant experience or skills",
                      "clarify": assessment["clarification"] or (
                          "This CV indicates this requirement is unmet. Has that changed?"
                          if issue == "unmet requirement" else
                          "Can you confirm this experience before adding it?" if not quote else ""),
                      "suggested_wording": quote if quote and issue != "unmet requirement" else ""})
        if len(edits) == 3:
            break
    return edits


def review_pool(job, profiles_df, rankings, checklist, provider=None):
    criteria = validate_checklist(checklist["criteria"], job.get("raw_description") or "")
    if profiles_df.empty or not criteria:
        raise ValueError("Add a CV and a reviewed job checklist first.")
    provider = provider or OpenAIProvider()
    reviews = []
    for _, profile in profiles_df.iterrows():
        sections = split_sections(profile.get("resume_text") or "")
        reviewed, omitted = sections[:MAX_SECTIONS], sections[MAX_SECTIONS:]
        issues = extraction_issues(profile)
        warnings = extraction_warnings(profile)
        match = rankings[rankings["profile_id"] == int(profile["id"])]
        overlap = int(match.iloc[0]["matched"]) if not match.empty else 0
        answers, validation_issues = [], []
        for section in reviewed:
            parsed, affected = request_assessments(
                provider, assessment_prompt(job, criteria, profile, section, overlap),
                criteria, section["text"], int(profile["id"]))
            answers.append(parsed)
            validation_issues.extend(f"{section['id']}: unverifiable evidence for {identifier}"
                                     for identifier in affected)
        incomplete = bool(issues or omitted or not reviewed or validation_issues)
        metadata = lambda chunk: {key: chunk[key] for key in ("id", "start", "end", "label")}
        combined = combine_assessments(criteria, answers, incomplete)
        if not incomplete:
            combined, affected = reconcile_duration(job, profile, criteria, answers, combined, provider)
            validation_issues.extend(f"duration review: unverifiable evidence for {identifier}"
                                     for identifier in affected)
            incomplete = bool(validation_issues)
        reviews.append({"profile_id": int(profile["id"]),
                        "profile_name": str(profile.get("profile_name") or ""),
                        "complete": not incomplete, "extraction_issues": issues,
                        "validation_issues": validation_issues,
                        "extraction_warnings": warnings,
                        "reviewed_sections": [metadata(chunk) for chunk in reviewed],
                        "omitted_sections": [metadata(chunk) for chunk in omitted],
                        "assessments": combined})
    selected_id, ties = rank_reviews(reviews, criteria)
    selected = next((review for review in reviews if review["profile_id"] == selected_id), None)
    incomplete_names = [review["profile_name"] for review in reviews if not review["complete"]]
    if selected:
        required = evidence_score(selected, criteria, "Required")[0]
        preferred = evidence_score(selected, criteria, "Preferred")[0]
        by_id = {item["criterion_id"]: item for item in selected["assessments"]}
        evidence = [f"{item['criterion']} ({by_id[item['id']]['status']})"
                    for item in criteria if item["kind"] == "Required"]
        reason = (f"Required evidence: {required} points; preferred evidence: {preferred} points. "
                  + ("Required criteria: " + "; ".join(evidence) + "." if evidence else ""))
    elif ties:
        reason = "The reviewable CVs are tied on required and preferred evidence."
    else:
        reason = "No CV was fully reviewable. Check extraction and omitted sections before choosing."
    return {"schema_version": SCHEMA, "rules_version": RULES,
            "guidance": {"checklist": checklist.get("guidance_hash", ""),
                         "evidence": guidance_hash("cv-evidence-review", "cv-evidence-system", "cv-duration-merge")},
            "checklist_version": checklist["version"], "selected_profile_id": selected_id,
            "tied_profile_ids": ties, "provisional": bool(incomplete_names),
            "incomplete_profiles": incomplete_names, "reason": reason,
            "cv_reviews": reviews, "suggestions": build_edits(selected, criteria)}
