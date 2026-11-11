"""Lightweight local resume skill extraction for profile and gap analysis."""

from __future__ import annotations

import re

from Scripts.skill_taxonomy import SKILL_HINTS, normalize_skill_name


def extract_resume_skills(resume_text: str) -> list[dict[str, str]]:
    """Return canonical taxonomy skills found in resume text."""

    text = str(resume_text or "").lower()
    found = []
    seen = set()

    for basket, hints in SKILL_HINTS.items():
        for hint in hints:
            pattern = rf"(?<![a-z0-9]){re.escape(hint.lower())}(?![a-z0-9])"
            if not re.search(pattern, text):
                continue

            key = (hint.lower(), basket.lower())
            if key in seen:
                continue

            seen.add(key)
            found.append(
                {
                    "skill": normalize_skill_name(hint),
                    "raw_skill": hint,
                    "basket": basket,
                }
            )

    return sorted(found, key=lambda item: (item["basket"], item["skill"].lower()))
