"""Shared prompt loading for interactive and batch job extraction."""

from pathlib import Path


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "job-extraction-prompt.md"


def build_extraction_prompt(job_description: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("[PASTE JOB DESCRIPTION HERE]", job_description)
