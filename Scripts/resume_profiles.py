"""Category labels for uploaded source CVs."""

from pathlib import Path

PROFILE_CATEGORIES = (
    "General",
    "IT Support",
    "Networking",
    "Systems Administration",
    "Infrastructure",
    "Data Centre",
    "Cloud",
    "Cybersecurity",
    "Telecommunications",
    "Other",
)

def category_from_filename(filename):
    stem = Path(filename or "").stem.lower().replace("_", " ").replace("-", " ")
    for words, category in (
        (("network", "routing"), "Networking"),
        (("sysadmin", "sys admin", "system admin", "systems", "server"), "Systems Administration"),
        (("support", "helpdesk", "service desk", "desktop"), "IT Support"),
        (("infrastructure",), "Infrastructure"),
        (("cloud", "azure", "aws"), "Cloud"),
        (("cyber", "security", "soc"), "Cybersecurity"),
    ):
        if any(word in stem for word in words):
            return category
    return "General"
