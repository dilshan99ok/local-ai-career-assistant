"""Canonical demand summaries for Skills Intelligence."""

from __future__ import annotations

import pandas as pd

from Scripts.skill_taxonomy import normalize_certification_name, normalize_skill_name


def canonicalize_skill_rows(rows: pd.DataFrame, custom_rules=None) -> pd.DataFrame:
    """Add canonical names while preserving every raw row."""

    result = rows.copy()
    if result.empty:
        result["canonical_skill"] = pd.Series(dtype=str)
        return result

    custom_rules = custom_rules or {}

    def canonical_value(row):
        candidates = [
            str(row.get("specific_skill", "") or "").strip().lower(),
            str(row.get("raw_skill", "") or "").strip().lower(),
        ]
        for candidate in candidates:
            if candidate in custom_rules:
                return custom_rules[candidate]
        return normalize_skill_name(row.get("raw_skill", ""), row.get("specific_skill", ""))

    result["canonical_skill"] = result.apply(canonical_value, axis=1)
    return result


def build_skill_demand_summary(rows: pd.DataFrame, custom_rules=None) -> pd.DataFrame:
    """Return one row per canonical skill with job-level demand metrics."""

    canonical = canonicalize_skill_rows(rows, custom_rules=custom_rules)
    if canonical.empty:
        return pd.DataFrame(
            columns=[
                "Skill",
                "Category",
                "Jobs",
                "Job Share",
                "Occurrences",
                "Last Seen",
            ]
        )

    total_jobs = canonical["job_id"].nunique()
    summary = (
        canonical.groupby("canonical_skill", dropna=False)
        .agg(
            Category=("skill_basket", lambda values: ", ".join(sorted(set(values.dropna())))),
            Jobs=("job_id", "nunique"),
            Occurrences=("canonical_skill", "size"),
            **{"Last Seen": ("created_at", "max")},
        )
        .reset_index()
        .rename(columns={"canonical_skill": "Skill"})
    )
    summary["Job Share"] = (summary["Jobs"] / total_jobs * 100).round(1)
    return summary.sort_values(
        by=["Jobs", "Occurrences", "Skill"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_certification_summary(rows: pd.DataFrame, custom_rules=None) -> pd.DataFrame:
    """Return one consolidated row per canonical certification."""

    if rows.empty:
        return pd.DataFrame(
            columns=[
                "Certification",
                "Jobs",
                "Job Share",
                "Related Areas",
                "Requirement Levels",
                "Last Seen",
            ]
        )

    canonical = rows.copy()
    custom_rules = custom_rules or {}
    canonical["canonical_certification"] = canonical.apply(
        lambda row: custom_rules.get(
            str(row.get("certification_name", "") or "").strip().lower(),
            custom_rules.get(
                str(row.get("raw_certification", "") or "").strip().lower(),
                normalize_certification_name(
                    row.get("raw_certification", ""),
                    row.get("certification_name", ""),
                ),
            ),
        ),
        axis=1,
    )
    total_jobs = canonical["job_id"].nunique()
    summary = (
        canonical.groupby("canonical_certification", dropna=False)
        .agg(
            Jobs=("job_id", "nunique"),
            **{
                "Related Areas": (
                    "related_basket",
                    lambda values: ", ".join(sorted(set(values.dropna()))),
                ),
                "Requirement Levels": (
                    "requirement_level",
                    lambda values: ", ".join(sorted(set(values.dropna()))),
                ),
                **{"Last Seen": ("created_at", "max")},
            },
        )
        .reset_index()
        .rename(columns={"canonical_certification": "Certification"})
    )
    summary["Job Share"] = (summary["Jobs"] / total_jobs * 100).round(1)
    return summary.sort_values(
        by=["Jobs", "Certification"],
        ascending=[False, True],
    ).reset_index(drop=True)


def find_skill_variants(rows: pd.DataFrame, custom_rules=None) -> pd.DataFrame:
    """Return canonical skills that have multiple raw spellings."""

    canonical = canonicalize_skill_rows(rows, custom_rules=custom_rules)
    if canonical.empty:
        return pd.DataFrame(columns=["Canonical Skill", "Raw Variants", "Variant Count"])

    variants = (
        canonical.groupby("canonical_skill")
        .agg(
            **{
                "Raw Variants": (
                    "specific_skill",
                    lambda values: ", ".join(sorted(set(str(value) for value in values))),
                )
            }
        )
        .reset_index()
        .rename(columns={"canonical_skill": "Canonical Skill"})
    )
    variants["Variant Count"] = variants["Raw Variants"].str.count(",") + 1
    return variants[variants["Variant Count"] > 1].sort_values(
        ["Variant Count", "Canonical Skill"], ascending=[False, True]
    )
