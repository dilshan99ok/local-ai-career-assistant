"""Resume and cover-letter tailoring prompts and generation helpers."""

from __future__ import annotations

import json

from Scripts.ai_provider import OpenAIProvider
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
    lines.extend(["", "## Priority edits"])
    if not context["edits"]:
        lines.append("No priority edits were identified in this CV review.")
    for index, edit in enumerate(context["edits"], 1):
        lines.extend([
            f"{index}. **{edit['criterion']}** ({edit['kind']}; {edit['issue_type']})",
            f"   - Where: {edit['edit_section']}",
        ])
        if edit["suggested_wording"]:
            lines.append(f"   - Supported CV wording: {edit['suggested_wording']}")
        if edit["clarify"]:
            lines.append(f"   - Confirm first: {edit['clarify']}")
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
    if mode == "Tailored draft":
        task = (
            "Create a complete tailored resume draft. Preserve all facts from the original resume, "
            "do not invent employers, dates, qualifications, tools, achievements, or metrics, and "
            "use the job's terminology only where it is truthful."
        )
    else:
        task = (
            "Create an actionable resume change plan. Include: overall fit summary, missing or weak "
            "skills, recommended summary changes, bullet-point rewrites, keyword suggestions, ATS "
            "risks, and a short list of claims that must not be added without evidence. Do not invent "
            "experience or qualifications."
        )

    review_instructions = (
        "Use the saved screening review below as the starting assessment. Apply its prioritized "
        "edits and criterion evidence instead of repeating the screening analysis. Preserve the "
        "distinction between demonstrated, partial, missing, and unable-to-assess evidence. "
        "Treat unconfirmed facts as questions, not resume claims.\n\n"
        "SAVED SCREENING REVIEW\n" + json.dumps(screening_context, ensure_ascii=False)
        if screening_context else ""
    )

    return f"""
{task}

Return clean Markdown with headings and bullet points. This is an editing aid for the user, not a
final submission. Be specific and concise.

{review_instructions}

TARGET JOB
{_job_context(job)}

ORIGINAL RESUME
{resume_text}
""".strip()


def build_cover_letter_prompt(job: dict, resume_text: str, tone: str, length: str) -> str:
    return f"""
Write an editable cover letter for the target job below using only facts supported by the resume.
Do not invent experience, metrics, qualifications, company details, or relationships. Do not include
placeholders except [Hiring Manager] when no contact name is available. Use a {tone} tone and keep it
{length}. Return only the letter body with a greeting and closing.

TARGET JOB
{_job_context(job)}

RESUME
{resume_text}
""".strip()


def build_follow_up_email_prompt(job: dict, resume_text: str, application: dict | None = None) -> str:
    application = application or {}
    return f"""
Write a concise, professional follow-up email for an application to the target job below.
Use only facts supported by the resume and application details. Do not invent interview dates,
conversations, achievements, hiring timelines, or contact relationships. Do not pressure the
recipient. Return a subject line followed by the email body.

TARGET JOB
{_job_context(job)}

APPLICATION DETAILS
Applied: {application.get('date_applied', '')}
Contact name: {application.get('contact_name', '')}
Contact role: {application.get('contact_role', '')}

RESUME
{resume_text}
""".strip()


def generate_resume_tailoring(job: dict, resume_text: str, mode: str,
                             screening_context: dict | None = None) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_resume_tailoring_prompt(job, resume_text, mode, screening_context),
        instructions=(
            "You are a careful resume editor. Preserve truthfulness and clearly label suggestions."
        ),
    )


def generate_cover_letter(job: dict, resume_text: str, tone: str, length: str) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_cover_letter_prompt(job, resume_text, tone, length),
        instructions=(
            "You are a careful cover-letter editor. Use only evidence from the supplied resume."
        ),
    )


def generate_follow_up_email(job: dict, resume_text: str, application: dict | None = None) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_follow_up_email_prompt(job, resume_text, application),
        instructions=(
            "You are a careful job-search communication editor. Keep the message concise, truthful, "
            "and editable."
        ),
    )
