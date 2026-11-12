"""Shared OpenAI provider for structured job-description extraction."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values
from openai import OpenAI

from Scripts.chatgpt_auth import ChatGPTAuth, ChatGPTAuthError


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_VALUES = dotenv_values(BASE_DIR / ".env")

DEFAULT_MODEL = "gpt-6.1-sol"


def configured_model() -> str:
    return os.getenv("OPENAI_MODEL") or ENV_VALUES.get("OPENAI_MODEL") or DEFAULT_MODEL

JOB_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "recruiter_name": {"type": "string"},
        "parent_company": {"type": "string"},
        "end_client_name": {"type": "string"},
        "end_client_industry": {"type": "string"},
        "posting_type": {"type": "string"},
        "job_title": {"type": "string"},
        "domain": {
            "type": "string",
            "enum": [
                "IT Support",
                "Networking",
                "Cloud",
                "Cybersecurity",
                "Systems Administration",
                "Data Centre",
                "Infrastructure",
                "Telecommunications",
                "Other",
            ],
        },
        "location": {"type": "string"},
        "salary_range": {"type": "string"},
        "work_mode": {
            "type": "string",
            "enum": ["Not specified", "On-site", "Hybrid", "Remote"],
        },
        "technical_skills": {"type": "array", "items": {"type": "string"}},
        "soft_skills": {"type": "array", "items": {"type": "string"}},
        "tools_platforms": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
        "domain_specific_skills": {
            "type": "array",
            "items": {"type": "string"},
        },
        "responsibilities": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "company",
        "recruiter_name",
        "parent_company",
        "end_client_name",
        "end_client_industry",
        "posting_type",
        "job_title",
        "domain",
        "location",
        "salary_range",
        "work_mode",
        "technical_skills",
        "soft_skills",
        "tools_platforms",
        "certifications",
        "domain_specific_skills",
        "responsibilities",
    ],
    "additionalProperties": False,
}


class OpenAIProvider:
    """Calls OpenAI through the user's ChatGPT sign-in."""

    def __init__(self, model: str | None = None):
        self.model = model or configured_model()
        try:
            access_token = ChatGPTAuth().get_access_token()
        except ChatGPTAuthError as error:
            raise RuntimeError(str(error)) from error

        self.client = OpenAI(
            api_key=access_token,
            base_url="https://api.openai.com/v1",
            timeout=60.0,
            max_retries=1,
        )

    def extract_job_data(self, prompt: str) -> dict:
        """Return one validated JSON object for a job-description prompt."""

        output_chunks: list[str] = []
        completed = False
        stream = self.client.responses.create(
            model=self.model,
            instructions=(
                "Extract only information supported by the supplied job description. "
                "If a text value is not present, return an empty string; if a list "
                "value is not present, return an empty array. Use Other when the "
                "job's domain cannot be confidently selected. "
                "Preserve the complete advertised job title, including any "
                "seniority or level prefix such as Junior, Senior, Graduate, "
                "Associate, Lead, Principal, or Staff. "
                "Do not infer company details, skills, certifications, or responsibilities."
                " When a recruiter or talent consultancy is named and the end client is undisclosed, use the recruiter as company and preserve the distinction in recruiter_name and end_client_name."
                " Extract location, salary range, and work mode only when explicitly supported by the posting."
            ),
            input=[{"role": "user", "content": prompt}],
            store=False,
            stream=True,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "job_description_extraction",
                    "strict": True,
                    "schema": JOB_EXTRACTION_SCHEMA,
                }
            },
        )

        try:
            for event in stream:
                if event.type == "response.output_text.delta":
                    output_chunks.append(event.delta)
                elif event.type == "response.failed":
                    error = event.response.error
                    message = error.message if error else "OpenAI response failed."
                    raise RuntimeError(message)
                elif event.type == "response.completed":
                    completed = True
        finally:
            stream.close()

        if not completed:
            raise RuntimeError("OpenAI response ended before completion.")

        raw_output = "".join(output_chunks)
        if not raw_output:
            raise RuntimeError("OpenAI returned no structured extraction output.")

        try:
            extracted_data = json.loads(raw_output)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenAI returned invalid structured JSON.") from error

        if not isinstance(extracted_data, dict):
            raise RuntimeError("OpenAI returned structured data in an unexpected shape.")

        return extracted_data

    def generate_text(self, prompt: str, instructions: str = "") -> str:
        """Generate editable text for tailoring workflows without hosted storage."""

        output_chunks: list[str] = []
        completed = False
        stream = self.client.responses.create(
            model=self.model,
            instructions=instructions or "Return only the requested editable content.",
            input=[{"role": "user", "content": prompt}],
            store=False,
            stream=True,
        )

        try:
            for event in stream:
                if event.type == "response.output_text.delta":
                    output_chunks.append(event.delta)
                elif event.type == "response.failed":
                    error = event.response.error
                    message = error.message if error else "OpenAI response failed."
                    raise RuntimeError(message)
                elif event.type == "response.completed":
                    completed = True
        finally:
            stream.close()

        if not completed:
            raise RuntimeError("OpenAI response ended before completion.")

        text = "".join(output_chunks).strip()
        if not text:
            raise RuntimeError("OpenAI returned no tailoring content.")
        return text
