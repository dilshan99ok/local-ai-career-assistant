"""Resume and cover-letter tailoring prompts and generation helpers."""

from __future__ import annotations

import json

from Scripts.ai_provider import OpenAIProvider
from Scripts.prompt_loader import load_prompt, render_prompt
from Scripts.resume_recommendation import build_edits, required_criteria_summary


def _job_context(job: dict) -> str:
    return (
        f"Company: {job.get('company', '')}\n"
        f"Job title: {job.get('job_title', '')}\n"
        f"Domain: {job.get('domain', '')}\n"
        f"Location: {job.get('location', '')}\n"
        f"Job description:\n{job.get('raw_description', '')}"
    )


def build_screening_context(checklist: dict | None, recommendation: dict | None, profile_id: int) -> dict | None:
    """Reuse a complete, cached screening review for the selected base CV."""
    if (not checklist or not recommendation
            or checklist.get("version") != recommendation.get("checklist_version")):
        return None
    review = next(
        (item for item in recommendation.get("cv_reviews", [])
         if int(item["profile_id"]) == int(profile_id)), None,
    )
    if not review or not review.get("complete"):
        return None
    criteria = checklist.get("criteria", [])
    assessments = {item["criterion_id"]: item for item in review.get("assessments", [])}
    if not criteria or {item["id"] for item in criteria} != set(assessments):
        return None
    return {
        "profile_id": int(profile_id),
        "checklist_version": checklist["version"],
        "provisional_pool": bool(recommendation.get("provisional")),
        "extraction_diagnostics": {
            "issues": review.get("extraction_issues", []),
            "warnings": review.get("extraction_warnings", []),
            "omitted_sections": review.get("omitted_sections", []),
        },
        "required_summary": required_criteria_summary(review, criteria),
        "criteria": [
            {**{key: criterion.get(key, "") for key in (
                "id", "kind", "criterion", "source", "requested_level", "alternatives")},
             **{key: assessments[criterion["id"]].get(key, "") for key in (
                 "status", "reason", "evidence", "issue_type", "edit_section", "clarification")}}
            for criterion in criteria
        ],
        "edits": build_edits(review, criteria),
    }


def format_screening_suggestions(context: dict) -> str:
    """Turn reviewed findings into an editable plan without another AI call."""
    summary = context["required_summary"]
    lines = ["# Resume changes from saved screening review", ""]
    if summary["total"]:
        lines.append(f"Required criteria demonstrated: {summary['demonstrated']} of {summary['total']}.")
    else:
        lines.append("No required criteria were specified in the job checklist.")
    if context["provisional_pool"]:
        lines.append("The pool recommendation is provisional because another CV review is incomplete.")
    diagnostics = context.get("extraction_diagnostics", {})
    if diagnostics.get("issues") or diagnostics.get("omitted_sections"):
        messages = list(diagnostics.get("issues", []))
        if diagnostics.get("omitted_sections"):
            messages.append(f"{len(diagnostics['omitted_sections'])} CV sections not reviewed")
        lines.append("Extraction or review scope needs checking: " + "; ".join(messages))
    lines.extend(["", "## Clarify or improve"])
    if not context["edits"]:
        lines.append("No unmet or partial criteria were identified in this CV review.")
    for index, edit in enumerate(context["edits"], 1):
        lines.extend([
            f"{index}. **{edit['criterion']}** ({edit['kind']}; {edit['issue_type']})",
            f"   - Where: {edit['edit_section']}",
        ])
        if edit["suggested_wording"]:
            lines.append(f"   - Existing CV excerpt: {edit['suggested_wording']}")
        if edit["clarify"]:
            lines.append(f"   - Confirm first: {edit['clarify']}")
        else:
            lines.append("   - Confirm first: Does the excerpt meet the full requirement and requested level?")
    strengths = [item for item in context["criteria"]
                 if item["kind"] in {"Required", "Preferred"}
                 and item["status"] == "Demonstrated" and item["evidence"]]
    if strengths:
        lines.extend(["", "## Evidence to bring forward"])
        for item in strengths:
            lines.append(f"- **{item['kind']}: {item['criterion']}** — {item['evidence']}")
    edited_ids = {item["criterion_id"] for item in context["edits"]}
    other_findings = [item for item in context["criteria"]
                      if item["kind"] in {"Required", "Preferred"}
                      and item["status"] != "Demonstrated"
                      and item["id"] not in edited_ids]
    if other_findings:
        lines.extend(["", "## Other checklist findings"])
    for item in other_findings:
        lines.append(f"- **{item['kind']} · {item['status']}:** {item['criterion']}")
    screening = [item for item in context["criteria"] if item["kind"] == "Screening"]
    if screening:
        lines.extend(["", "## Screening conditions to confirm"])
        for item in screening:
            lines.append(f"- **{item['status']}:** {item['criterion']}")
    lines.extend(["", "Only add claims you can verify. A missing CV mention does not prove you lack the experience."])
    return "\n".join(lines)


def build_resume_tailoring_prompt(job: dict, resume_text: str, mode: str,
                                  screening_context: dict | None = None) -> str:
    review_instructions = (
        render_prompt("resume-screening-review", SCREENING_JSON=json.dumps(screening_context, ensure_ascii=False))
        if screening_context else ""
    )
    return render_prompt(
        "resume-draft" if mode == "Tailored draft" else "resume-suggestions",
        SCREENING_REVIEW=review_instructions, JOB_CONTEXT=_job_context(job), RESUME_TEXT=resume_text,
    )


def build_cover_letter_prompt(job: dict, resume_text: str, tone: str, length: str) -> str:
    return render_prompt("cover-letter", TONE=tone, LENGTH=length,
                         JOB_CONTEXT=_job_context(job), RESUME_TEXT=resume_text)


def build_follow_up_email_prompt(job: dict, resume_text: str, application: dict | None = None) -> str:
    application = application or {}
    return render_prompt(
        "follow-up-email", JOB_CONTEXT=_job_context(job),
        DATE_APPLIED=application.get("date_applied") or "",
        CONTACT_NAME=application.get("contact_name") or "",
        CONTACT_ROLE=application.get("contact_role") or "", RESUME_TEXT=resume_text,
    )


def generate_resume_tailoring(job: dict, resume_text: str, mode: str,
                             screening_context: dict | None = None) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_resume_tailoring_prompt(job, resume_text, mode, screening_context),
        instructions=load_prompt("resume-editor-system"),
    )


def generate_cover_letter(job: dict, resume_text: str, tone: str, length: str) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_cover_letter_prompt(job, resume_text, tone, length),
        instructions=load_prompt("cover-letter-system"),
    )


def generate_follow_up_email(job: dict, resume_text: str, application: dict | None = None) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_follow_up_email_prompt(job, resume_text, application),
        instructions=load_prompt("follow-up-system"),
    )
