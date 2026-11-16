"""Load versioned AI guidance from the project's Markdown prompt library."""

from pathlib import Path
import re


PROMPT_DIR = Path(__file__).resolve().parent.parent / "Prompts"
PROMPT_PATH = PROMPT_DIR / "job-extraction-prompt.md"


def load_prompt(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError(f"Invalid prompt name: {name}")
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


def render_prompt(name: str, **values: object) -> str:
    """Replace {{UPPERCASE_KEYS}} once, leaving supplied job/CV text untouched."""
    template = load_prompt(name)
    placeholders = re.findall(r"\{\{([^{}]+)\}\}", template)
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) for key in placeholders):
        raise ValueError(f"Prompt {name} contains an invalid placeholder")
    keys = set(placeholders)
    if keys != set(values):
        raise ValueError(f"Prompt {name} expects {sorted(keys)}, received {sorted(values)}")
    return re.sub(r"\{\{([A-Z][A-Z0-9_]*)\}\}",
                  lambda match: str(values[match.group(1)]), template)


def build_extraction_prompt(job_description: str) -> str:
    return render_prompt("job-extraction-prompt", JOB_DESCRIPTION=job_description)
