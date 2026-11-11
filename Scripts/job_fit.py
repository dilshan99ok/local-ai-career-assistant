"""Shared, deterministic job-to-resume fit calculations."""

from __future__ import annotations

import json

import pandas as pd

from Scripts.skill_analysis import canonicalize_skill_rows
from Scripts.skill_taxonomy import normalize_skill_name
from Scripts.resume_profiles import choose_profile


def clean_value(value) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def parse_resume_skills(profile_row) -> set[str]:
    if profile_row is None:
        return set()
    try:
        raw_skills = json.loads(profile_row.get("skills_json", "[]"))
    except (TypeError, json.JSONDecodeError):
        raw_skills = []

    known = set()
    for item in raw_skills:
        if not isinstance(item, dict):
            continue
        for key in ("skill", "raw_skill", "specific_skill"):
            value = clean_value(item.get(key))
            if value:
                known.add(normalize_skill_name(value, value).lower())
    return known


def selected_profile(profiles_df, job_domain=""):
    return choose_profile(profiles_df, job_domain)


def build_fit_snapshot(skills_df, profiles_df, job_domain=""):
    empty = {
        "score": None,
        "requested": pd.DataFrame(),
        "matched": pd.DataFrame(),
        "missing": pd.DataFrame(),
        "profile_name": "",
    }
    if skills_df is None or skills_df.empty:
        return empty

    canonical = canonicalize_skill_rows(skills_df)
    if canonical.empty:
        return empty

    profile_row = selected_profile(profiles_df, job_domain)
    known_skills = parse_resume_skills(profile_row)
    canonical["is_matched"] = canonical["canonical_skill"].apply(
        lambda value: normalize_skill_name(value, value).lower() in known_skills
    )
    requested = canonical.drop_duplicates("canonical_skill").copy()
    matched = requested[requested["is_matched"]].copy()
    missing = requested[~requested["is_matched"]].copy()
    score = round(len(matched) / len(requested) * 100) if len(requested) and profile_row is not None else None

    return {
        "score": score,
        "requested": requested,
        "matched": matched,
        "missing": missing,
        "profile_name": clean_value(profile_row.get("profile_name")) if profile_row is not None else "",
    }


def fit_label(score) -> str:
    if score is None:
        return "Add resume"
    if score >= 80:
        return "Strong match"
    if score >= 60:
        return "Promising"
    if score >= 40:
        return "Partial match"
    return "Needs work"


def fit_display(score) -> str:
    if score is None:
        return "Add resume"
    short_label = {
        "Strong match": "Strong",
        "Promising": "Promising",
        "Partial match": "Partial",
        "Needs work": "Needs work",
    }[fit_label(score)]
    return f"{int(score)}% · {short_label}"


def build_job_fit_summary(jobs_df, skill_rows_df, profiles_df) -> pd.DataFrame:
    columns = ["job_id", "fit_score", "fit_status", "fit_display", "matched_skills", "requested_skills"]
    if jobs_df is None or jobs_df.empty:
        return pd.DataFrame(columns=columns)

    skill_groups = {}
    if skill_rows_df is not None and not skill_rows_df.empty:
        skill_groups = {job_id: rows for job_id, rows in skill_rows_df.groupby("job_id")}

    rows = []
    for _, job in jobs_df.iterrows():
        job_id = job["id"]
        snapshot = build_fit_snapshot(
            skill_groups.get(job_id, pd.DataFrame()), profiles_df, job.get("domain", "")
        )
        score = snapshot["score"]
        rows.append(
            {
                "job_id": int(job_id),
                "fit_score": score,
                "fit_status": fit_label(score),
                "fit_display": fit_display(score),
                "matched_skills": len(snapshot["matched"]),
                "requested_skills": len(snapshot["requested"]),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def attach_fit_scores(jobs_df, skill_rows_df, profiles_df):
    if jobs_df is None or jobs_df.empty:
        return jobs_df.copy() if jobs_df is not None else pd.DataFrame()
    summary = build_job_fit_summary(jobs_df, skill_rows_df, profiles_df)
    return jobs_df.merge(summary, left_on="id", right_on="job_id", how="left").drop(columns=["job_id"])
