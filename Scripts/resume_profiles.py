"""Category labels and default source CV selection for saved jobs."""

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

RELATED_CATEGORIES = {
    "Telecommunications": ("Networking",),
    "Data Centre": ("Infrastructure", "Systems Administration", "Networking"),
    "Infrastructure": ("Systems Administration", "Networking"),
}


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


def choose_profile(profiles_df, job_domain=""):
    """Prefer a category CV, then a general CV, then the active CV."""
    if profiles_df is None or profiles_df.empty:
        return None
    categories = (job_domain, *RELATED_CATEGORIES.get(job_domain, ()), "General")
    if "target_domain" in profiles_df.columns:
        for category in categories:
            if not category:
                continue
            matches = profiles_df[profiles_df["target_domain"].fillna("General") == category]
            if not matches.empty:
                return matches.sort_values("updated_at", ascending=False).iloc[0]
    active = profiles_df[profiles_df["is_active"] == 1]
    return active.iloc[0] if not active.empty else profiles_df.iloc[0]
