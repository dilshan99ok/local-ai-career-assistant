"""Resume and cover-letter tailoring prompts and generation helpers."""

from __future__ import annotations

from Scripts.ai_provider import OpenAIProvider


def _job_context(job: dict) -> str:
    return (
        f"Company: {job.get('company', '')}\n"
        f"Job title: {job.get('job_title', '')}\n"
        f"Domain: {job.get('domain', '')}\n"
        f"Location: {job.get('location', '')}\n"
        f"Job description:\n{job.get('raw_description', '')}"
    )


def build_resume_tailoring_prompt(job: dict, resume_text: str, mode: str) -> str:
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

    return f"""
{task}

Return clean Markdown with headings and bullet points. This is an editing aid for the user, not a
final submission. Be specific and concise.

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


def generate_resume_tailoring(job: dict, resume_text: str, mode: str) -> str:
    provider = OpenAIProvider()
    return provider.generate_text(
        build_resume_tailoring_prompt(job, resume_text, mode),
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
