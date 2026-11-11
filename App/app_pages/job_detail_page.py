import pandas as pd
import streamlit as st

from App.app_utils.database import (
    get_applications_for_job_df,
    get_application_messages_df,
    get_cover_letter_versions_df,
    get_job_certifications_for_job_df,
    get_job_detail_df,
    get_job_skills_for_job_df,
    get_resume_profiles_df,
    get_resume_versions_df,
    update_application_status,
)
from Scripts.job_fit import build_fit_snapshot
from Scripts.resume_export import build_resume_docx, safe_resume_filename
from App.app_utils.navigation import go_back, navigate_to
from Scripts.skill_analysis import build_certification_summary, canonicalize_skill_rows


STATUS_LABELS = {
    "Applied": "🔵 Applied",
    "Interview": "🟡 Interview",
    "Offer": "🟢 Offer",
    "Rejected": "🔴 Rejected",
    "Withdrawn": "⚪ Withdrawn",
    "No Response": "🟣 No response",
    "Archived": "⚫ Archived",
}


def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def go_to_jobs():
    go_back(fallback="Jobs")


def go_to_tailoring(job_id):
    navigate_to("Tailoring Studio", job_id=int(job_id))


def render_fit_metric(fit):
    score = fit["score"]
    if score is None:
        st.metric("Resume fit", "—", help="Create a resume profile to calculate a local skill comparison.")
    else:
        st.metric("Resume fit", f"{score}%", help="Distinct extracted job skills found in the selected resume profile.")


def render_job_header(job, job_id, applications_df, fit):
    if not st.session_state.get("navigation_history"):
        if st.button("← Back to Jobs", key="back_to_jobs"):
            go_to_jobs()

    title = clean_value(job.get("job_title")) or "Untitled role"
    company = clean_value(job.get("company")) or "Unknown company"
    domain = clean_value(job.get("domain")) or "Unclassified"
    st.title(title)
    st.caption(f"{company}  ·  {domain}")

    recruiter = clean_value(job.get("recruiter_name"))
    parent = clean_value(job.get("parent_company"))
    client = clean_value(job.get("end_client_name"))
    client_industry = clean_value(job.get("end_client_industry"))
    if recruiter or client or client_industry:
        relationship = []
        if recruiter:
            relationship.append(f"Recruiter: {recruiter}")
        if parent:
            relationship.append(f"Parent: {parent}")
        if client:
            relationship.append(f"End client: {client}")
        elif client_industry:
            relationship.append(f"End client industry: {client_industry}")
        st.info(" · ".join(relationship))

    applications_label = "Not applied"
    follow_up = "—"
    if not applications_df.empty:
        application = applications_df.iloc[0]
        applications_label = STATUS_LABELS.get(
            clean_value(application.get("current_status")),
            clean_value(application.get("current_status")) or "Unknown",
        )
        follow_up = clean_value(application.get("follow_up_date")) or "—"

    action_col1, action_col2, action_col3 = st.columns([1.35, 1.55, 3.3])
    if action_col1.button("Tailor application", key=f"workspace_tailor_{job_id}", use_container_width=True):
        go_to_tailoring(job_id)
    if action_col2.button("Add / update application", key=f"workspace_application_{job_id}", use_container_width=True):
        if applications_df.empty:
            st.session_state["open_add_application"] = True
        else:
            st.session_state["editing_application_id"] = int(applications_df.iloc[0]["id"])
        navigate_to("Applications")
    source_url = clean_value(job.get("source_url"))
    if source_url:
        action_col3.link_button("Open original posting", source_url)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        render_fit_metric(fit)
    metric_col2.metric("Application", applications_label)
    metric_col3.metric("Follow-up", follow_up)
    metric_col4.metric("Skills identified", len(fit["requested"]))


def render_overview_tab(job, skills_df):
    left, right = st.columns([1.1, 1.9])
    with left:
        st.subheader("Role snapshot")
        snapshot = {
            "Location": clean_value(job.get("location")) or "Not specified",
            "Work mode": clean_value(job.get("work_mode")) or "Not specified",
            "Salary": clean_value(job.get("salary_range")) or "Not specified",
            "Source": clean_value(job.get("application_source")) or "Not specified",
            "Analyzed": (clean_value(job.get("analyzed_at")) or clean_value(job.get("created_at")))[:16] or "—",
        }
        for label, value in snapshot.items():
            st.markdown(f"**{label}**  \n{value}")

    with right:
        st.subheader("What this role emphasizes")
        if skills_df.empty:
            st.info("No structured skills were extracted for this role.")
        else:
            skills = canonicalize_skill_rows(skills_df)
            baskets = skills["skill_basket"].dropna().drop_duplicates().tolist()
            if baskets:
                st.markdown("  ".join(f"`{basket}`" for basket in baskets))
            visible = [column for column in ["canonical_skill", "requirement_level"] if column in skills.columns]
            if visible:
                st.dataframe(
                    skills[visible].drop_duplicates().rename(
                        columns={"canonical_skill": "Skill", "requirement_level": "Requirement"}
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

    raw_description = clean_value(job.get("raw_description"))
    with st.expander("View original job description", expanded=False):
        if raw_description:
            st.text_area("Original job description", value=raw_description, height=460, disabled=True, label_visibility="collapsed")
        else:
            st.warning("The original job description was not retained for this older record.")


def render_fit_tab(fit, profiles_df):
    st.subheader("Resume fit and skill gaps")
    if not profiles_df.empty:
        st.caption(f"Compared against: {fit['profile_name'] or 'selected resume profile'}")
    else:
        st.info("Create a resume profile in Resume & Gaps to compare your evidence with this role.")
        if st.button("Open Resume & Gaps", key="open_resume_from_fit"):
            navigate_to("Resume & Gaps")

    score = fit["score"]
    if score is not None:
        st.progress(score / 100, text=f"{score}% of the extracted skills are represented in the selected resume")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Matched skills", len(fit["matched"]))
    metric_col2.metric("Potential gaps", len(fit["missing"]))
    metric_col3.metric("Requested skills", len(fit["requested"]))

    matched_tab, gaps_tab = st.tabs(["Already demonstrated", "Potential gaps"])
    with matched_tab:
        if fit["matched"].empty:
            st.info("No exact skill matches were found in the selected resume profile.")
        else:
            st.dataframe(
                fit["matched"][["canonical_skill", "skill_basket"]].drop_duplicates().rename(
                    columns={"canonical_skill": "Skill", "skill_basket": "Category"}
                ),
                use_container_width=True,
                hide_index=True,
            )
    with gaps_tab:
        if fit["missing"].empty:
            st.success("No extracted skill gaps were identified.")
        else:
            st.dataframe(
                fit["missing"][["canonical_skill", "skill_basket", "requirement_level"]].drop_duplicates().rename(
                    columns={"canonical_skill": "Skill", "skill_basket": "Category", "requirement_level": "Requirement"}
                ),
                use_container_width=True,
                hide_index=True,
            )


def render_packet_tab(job_id, applications_df):
    st.subheader("Application packet")

    application_id = int(applications_df.iloc[0]["id"]) if not applications_df.empty else None
    resume_versions = get_resume_versions_df()
    linked_resume = resume_versions[
        (resume_versions["target_job_id"] == job_id)
        & (resume_versions["source_type"] == "tailored")
        & (resume_versions["change_summary"].fillna("") != "Suggestions")
    ] if not resume_versions.empty else pd.DataFrame()
    cover_versions = get_cover_letter_versions_df(job_id=job_id, application_id=application_id)
    follow_up_messages = get_application_messages_df(
        job_id=job_id,
        application_id=application_id,
        message_type="follow_up_email",
    )

    resume_col, cover_col, follow_col = st.columns(3)
    with resume_col:
        st.markdown("#### Resume")
        if linked_resume.empty:
            st.info("No job-specific resume version yet.")
        else:
            latest = linked_resume.iloc[0]
            st.success(clean_value(latest["version_name"]))
            st.caption(
                f"From {clean_value(latest.get('source_profile_name')) or 'source CV'} · "
                f"Saved {clean_value(latest['created_at'])[:16]}"
            )
            st.download_button(
                "Download CV (.docx)",
                data=build_resume_docx(latest["content"]),
                file_name=safe_resume_filename(latest["version_name"]),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"job_detail_download_cv_{job_id}",
            )
    with cover_col:
        st.markdown("#### Cover letter")
        if cover_versions.empty:
            st.info("No cover letter version yet.")
        else:
            latest = cover_versions.iloc[0]
            st.success(clean_value(latest["version_name"]))
            st.caption(f"{clean_value(latest['status'])} · {clean_value(latest['created_at'])[:16]}")
    with follow_col:
        st.markdown("#### Follow-up")
        follow_up = clean_value(applications_df.iloc[0].get("follow_up_date")) if not applications_df.empty else ""
        st.info(follow_up or "Not scheduled")
        if follow_up_messages.empty:
            st.caption("No follow-up email saved yet.")
        else:
            latest_message = follow_up_messages.iloc[0]
            st.caption(f"Email: {clean_value(latest_message['status'])}")

    if st.button("Open Tailoring Studio", key=f"packet_tailoring_{job_id}"):
        go_to_tailoring(job_id)


def render_tracking_tab(applications_df):
    st.subheader("Application tracking")
    if applications_df.empty:
        st.info("No application has been linked to this job yet.")
        return

    for _, application in applications_df.iterrows():
        status = clean_value(application.get("current_status")) or "Unknown"
        with st.container(border=True):
            st.markdown(f"#### Application #{int(application['id'])} · {STATUS_LABELS.get(status, status)}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Applied", clean_value(application.get("date_applied")) or "—")
            col2.metric("Follow-up", clean_value(application.get("follow_up_date")) or "—")
            col3.metric("Contact", clean_value(application.get("contact_name")) or "—")
            col4.metric("Stage", clean_value(application.get("interview_stage")) or "—")
            contact_details = " · ".join(
                value for value in [
                    clean_value(application.get("contact_email")),
                    clean_value(application.get("contact_number")),
                    clean_value(application.get("contact_role")),
                ] if value
            )
            if contact_details:
                st.caption(contact_details)
            if clean_value(application.get("notes")):
                st.markdown(f"**Notes**  \n{clean_value(application.get('notes'))}")
            status_options = ["Applied", "Interview", "Offer", "Rejected", "Withdrawn", "No Response", "Archived"]
            status_col, action_col = st.columns([2, 1])
            with status_col:
                selected_status = st.selectbox(
                    "Application status",
                    status_options,
                    index=status_options.index(status) if status in status_options else 0,
                    key=f"workspace_status_{int(application['id'])}",
                )
            with action_col:
                if st.button("Save status", key=f"workspace_save_status_{int(application['id'])}"):
                    update_application_status(int(application["id"]), selected_status)
                    st.rerun()
            if st.button("Edit application", key=f"workspace_edit_application_{int(application['id'])}"):
                st.session_state["editing_application_id"] = int(application["id"])
                navigate_to("Applications")


def render_job_detail():
    job_id = st.session_state.get("selected_job_id")
    if not job_id:
        st.info("Open a job from the Jobs list to view its workspace.")
        if st.button("Go to Jobs"):
            go_to_jobs()
        return

    job_df = get_job_detail_df(job_id)
    if job_df.empty:
        st.error("This job could not be found.")
        if st.button("Back to Jobs"):
            go_to_jobs()
        return

    job = job_df.iloc[0].to_dict()
    skills_df = get_job_skills_for_job_df(job_id)
    certs_df = get_job_certifications_for_job_df(job_id)
    applications_df = get_applications_for_job_df(job.get("source_file", ""))
    profiles_df = get_resume_profiles_df()
    fit = build_fit_snapshot(skills_df, profiles_df, job.get("domain", ""))

    render_job_header(job, job_id, applications_df, fit)
    overview_tab, fit_tab, packet_tab, tracking_tab = st.tabs(
        ["Overview", "Fit & gaps", "Application packet", "Tracking"]
    )

    with overview_tab:
        render_overview_tab(job, skills_df)
        st.subheader("Certifications")
        if certs_df.empty:
            st.info("No certifications were extracted for this role.")
        else:
            st.dataframe(build_certification_summary(certs_df), use_container_width=True, hide_index=True)
    with fit_tab:
        render_fit_tab(fit, profiles_df)
    with packet_tab:
        render_packet_tab(job_id, applications_df)
    with tracking_tab:
        render_tracking_tab(applications_df)
