import json

import pandas as pd
import streamlit as st

from App.app_utils.database import (
    get_certification_demand_rows_df,
    get_certification_normalization_rules_df,
    get_applications_df,
    get_jobs_df,
    get_resume_profiles_df,
    get_skill_demand_rows_df,
    get_skill_normalization_rules_df,
    save_certification_normalization_rule,
    save_skill_normalization_rule,
)
from App.app_pages.opportunities_page import tracked_jobs
from Scripts.skill_analysis import (
    build_certification_summary,
    build_skill_demand_summary,
    canonicalize_skill_rows,
    find_skill_variants,
)
from Scripts.skill_taxonomy import normalize_certification_name, normalize_skill_name
from Scripts.skill_visual import build_skill_landscape_html


def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def load_custom_rules():
    skill_rules = get_skill_normalization_rules_df()
    cert_rules = get_certification_normalization_rules_df()
    skill_map = {
        clean_value(row["alias"]).lower(): row["canonical_skill"]
        for _, row in skill_rules.iterrows()
        if clean_value(row["alias"])
    }
    cert_map = {
        clean_value(row["alias"]).lower(): row["canonical_name"]
        for _, row in cert_rules.iterrows()
        if clean_value(row["alias"])
    }
    return skill_map, cert_map


def render_metrics(skill_summary, cert_summary, job_count):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Canonical skills", len(skill_summary))
    col2.metric("Skill categories", skill_summary["Category"].nunique() if not skill_summary.empty else 0)
    col3.metric("Certifications", len(cert_summary))
    col4.metric("Jobs analyzed", job_count)


def render_skill_overview(skill_rows, skill_summary, custom_rules):
    st.subheader("Skill landscape")
    if skill_summary.empty:
        st.info("No structured skill data is available yet.")
        return

    canonical_rows = canonicalize_skill_rows(skill_rows, custom_rules=custom_rules)
    st.iframe(build_skill_landscape_html(skill_summary, canonical_rows), height="content")

    with st.expander("Audit canonical skill data", expanded=False):
        st.dataframe(
            skill_summary.rename(
                columns={
                    "Jobs": "Jobs requiring skill",
                    "Job Share": "Job share (%)",
                    "Occurrences": "Raw occurrences",
                    "Last Seen": "Last seen",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    skill_options = ["Select a skill"] + skill_summary["Skill"].tolist()
    selected_skill = st.selectbox("Inspect skill evidence", skill_options, key="skill_detail_selector")
    if selected_skill == "Select a skill":
        return

    canonical_rows = canonicalize_skill_rows(skill_rows, custom_rules=custom_rules)
    detail = canonical_rows[canonical_rows["canonical_skill"] == selected_skill].copy()
    detail = detail.rename(
        columns={
            "company": "Company",
            "job_title": "Job Title",
            "domain": "Domain",
            "specific_skill": "Raw extracted value",
            "evidence_text": "Evidence",
            "requirement_level": "Requirement",
            "job_created_at": "Job date",
        }
    )
    visible = [
        column
        for column in [
            "Company",
            "Job Title",
            "Domain",
            "Raw extracted value",
            "Evidence",
            "Requirement",
            "Job date",
        ]
        if column in detail.columns
    ]
    st.dataframe(detail[visible], width="stretch", hide_index=True)


def render_certifications(cert_rows, cert_summary, custom_rules):
    st.subheader("Certification demand")
    if cert_summary.empty:
        st.info("No certification data is available yet.")
        return

    search = st.text_input(
        "Search certifications",
        placeholder="Search canonical certification or related area",
        key="canonical_certification_search",
    ).lower().strip()
    filtered = cert_summary.copy()
    if search:
        searchable = (
            filtered["Certification"].str.lower()
            + " "
            + filtered["Related Areas"].str.lower()
        )
        filtered = filtered[searchable.str.contains(search, regex=False)]

    st.dataframe(
        filtered.rename(
            columns={
                "Jobs": "Jobs mentioning certification",
                "Job Share": "Job share (%)",
                "Related Areas": "Related areas",
                "Requirement Levels": "Requirement levels",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    options = ["Select a certification"] + filtered["Certification"].tolist()
    selected = st.selectbox("Inspect certification evidence", options, key="certification_detail_selector")
    if selected == "Select a certification":
        return

    detail = cert_rows.copy()
    detail["Canonical Certification"] = detail.apply(
        lambda row: custom_rules.get(
            clean_value(row.get("certification_name")).lower(),
            normalize_certification_name(
                row.get("raw_certification", ""),
                row.get("certification_name", ""),
            ),
        ),
        axis=1,
    )
    detail = detail[detail["Canonical Certification"] == selected]
    detail = detail.rename(
        columns={
            "company": "Company",
            "job_title": "Job Title",
            "domain": "Domain",
            "related_basket": "Related area",
            "requirement_level": "Requirement",
            "evidence_text": "Evidence",
            "job_created_at": "Job date",
        }
    )
    visible = [
        column
        for column in [
            "Company",
            "Job Title",
            "Domain",
            "Related area",
            "Requirement",
            "Evidence",
            "Job date",
        ]
        if column in detail.columns
    ]
    st.dataframe(detail[visible], width="stretch", hide_index=True)


def render_skill_gaps(skill_summary):
    st.subheader("Resume skill gaps")
    profiles = get_resume_profiles_df()
    if profiles.empty:
        st.info("Create a resume profile in Resume & Gaps to compare your skills with market demand.")
        return

    options = {f"{row['profile_name']} · #{int(row['id'])}": row for _, row in profiles.iterrows()}
    selected = st.selectbox("Resume profile", list(options), key="skills_resume_selector")
    row = options[selected]
    try:
        resume_skills = json.loads(row["skills_json"])
    except (TypeError, json.JSONDecodeError):
        resume_skills = []

    known = {
        normalize_skill_name(item.get("raw_skill", ""), item.get("skill", "")).lower()
        for item in resume_skills
        if isinstance(item, dict)
    }
    gaps = skill_summary[~skill_summary["Skill"].str.lower().isin(known)].copy()
    gaps["Priority"] = gaps["Jobs"].rank(method="dense", ascending=False).astype(int)
    if gaps.empty:
        st.success("No gaps were identified from the current saved jobs.")
    else:
        st.dataframe(
            gaps.sort_values(["Priority", "Skill"]),
            width="stretch",
            hide_index=True,
        )


def render_data_quality(skill_rows, cert_rows, custom_skill_rules, custom_cert_rules):
    st.subheader("Data quality and normalization")
    if st.session_state.pop("skill_mapping_saved", False):
        st.success("Skill mapping saved.")
    if st.session_state.pop("certification_mapping_saved", False):
        st.success("Certification mapping saved.")
    variants = find_skill_variants(skill_rows, custom_rules=custom_skill_rules)
    if variants.empty:
        st.success("No unresolved skill variants were detected.")
    else:
        st.caption("These canonical skills have multiple raw spellings in the source data.")
        st.dataframe(variants, width="stretch", hide_index=True)

    with st.expander("Add or update a skill mapping", expanded=False):
        with st.form("skill_normalization_form", enter_to_submit=False):
            alias = st.text_input("Raw alias")
            canonical = st.text_input("Canonical skill")
            basket = st.text_input("Canonical category", value="Other")
            submitted = st.form_submit_button("Save skill mapping")
            if submitted:
                if alias.strip() and canonical.strip():
                    with st.spinner("Saving skill mapping…"):
                        save_skill_normalization_rule(alias, canonical, basket)
                    st.session_state["skill_mapping_saved"] = True
                    st.rerun()
                else:
                    st.error("Alias and canonical skill are required.")

    with st.expander("Add or update a certification mapping", expanded=False):
        with st.form("certification_normalization_form", enter_to_submit=False):
            alias = st.text_input("Certification alias")
            canonical = st.text_input("Canonical certification")
            submitted = st.form_submit_button("Save certification mapping")
            if submitted:
                if alias.strip() and canonical.strip():
                    with st.spinner("Saving certification mapping…"):
                        save_certification_normalization_rule(alias, canonical)
                    st.session_state["certification_mapping_saved"] = True
                    st.rerun()
                else:
                    st.error("Alias and canonical certification are required.")


def render_skills():
    st.title("Skills")

    jobs_df = tracked_jobs(get_jobs_df(), get_applications_df())
    skill_rows = get_skill_demand_rows_df()
    cert_rows = get_certification_demand_rows_df()
    skill_rows = skill_rows[skill_rows["job_id"].isin(jobs_df["id"])]
    cert_rows = cert_rows[cert_rows["job_id"].isin(jobs_df["id"])]
    custom_skill_rules, custom_cert_rules = load_custom_rules()

    domains = ["All"]
    if not skill_rows.empty:
        domains += sorted(
            value for value in skill_rows["domain"].dropna().unique().tolist() if clean_value(value)
        )
    selected_domain = st.selectbox("Domain filter", domains, key="skills_domain_filter")
    search = st.text_input(
        "Search skills or categories",
        placeholder="e.g. Microsoft, routing, cybersecurity",
        key="canonical_skill_search",
    ).lower().strip()

    filtered_skill_rows = skill_rows.copy()
    if selected_domain != "All":
        filtered_skill_rows = filtered_skill_rows[
            filtered_skill_rows["domain"] == selected_domain
        ]
    if search and not filtered_skill_rows.empty:
        searchable = (
            filtered_skill_rows["specific_skill"].fillna("").astype(str)
            + " "
            + filtered_skill_rows["raw_skill"].fillna("").astype(str)
            + " "
            + filtered_skill_rows["skill_basket"].fillna("").astype(str)
        ).str.lower()
        filtered_skill_rows = filtered_skill_rows[searchable.str.contains(search, regex=False)]

    skill_summary = build_skill_demand_summary(
        filtered_skill_rows,
        custom_rules=custom_skill_rules,
    )
    cert_summary = build_certification_summary(cert_rows, custom_rules=custom_cert_rules)

    render_metrics(skill_summary, cert_summary, len(jobs_df))
    st.download_button(
        "Download canonical skills CSV",
        data=skill_summary.to_csv(index=False).encode("utf-8"),
        file_name="canonical_skill_demand.csv",
        mime="text/csv",
        key="download_canonical_skills",
    )

    overview, certifications, gaps, quality = st.tabs(
        ["Market Overview", "Certifications", "Resume Gaps", "Data Quality"]
    )
    with overview:
        render_skill_overview(filtered_skill_rows, skill_summary, custom_skill_rules)
    with certifications:
        render_certifications(cert_rows, cert_summary, custom_cert_rules)
    with gaps:
        render_skill_gaps(skill_summary)
    with quality:
        render_data_quality(
            filtered_skill_rows,
            cert_rows,
            custom_skill_rules,
            custom_cert_rules,
        )
