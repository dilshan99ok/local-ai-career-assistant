import json
from datetime import date

import pandas as pd
import streamlit as st

from Scripts.ai_helper import (
    analyze_jd_with_openai,
    add_business_days,
    save_analyzed_application,
    build_extraction_warnings,
)

from App.app_utils.database import (
    get_applications_df,
    update_application,
    delete_application,
    get_application_status_history_df,
    get_follow_up_events_df,
    get_jobs_df,
    get_resume_profiles_df,
    get_skill_demand_rows_df,
    get_duplicate_applications,
)
from Scripts.job_fit import attach_fit_scores
from Scripts.job_url import JobPageFetchError, fetch_job_posting
from App.app_utils.navigation import navigate_to
from App.app_pages.opportunities_page import (
    build_opportunities_df, filter_opportunities, render_opportunities_table,
)

DOMAINS = [
    "IT Support",
    "Networking",
    "Cloud",
    "Cybersecurity",
    "Systems Administration",
    "Data Centre",
    "Infrastructure",
    "Telecommunications",
    "Other",
]

STATUSES = [
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
    "Withdrawn",
    "No Response",
    "Archived",
]

STATUS_DISPLAY = {
    "Applied": "🔵 Applied",
    "Interview": "🟡 Interview",
    "Offer": "🟢 Offer",
    "Rejected": "🔴 Rejected",
    "Withdrawn": "⚪ Withdrawn",
    "No Response": "🟣 No Response",
    "Archived": "⚫ Archived",
}


def parse_list_text(value):
    return [
        item.strip()
        for item in str(value or "").replace(",", "\n").splitlines()
        if item.strip()
    ]


def parse_date_value(value, fallback=None):
    if value is None:
        return fallback

    value = str(value).strip()

    if value == "" or value.lower() == "none":
        return fallback

    try:
        return pd.to_datetime(value).date()
    except Exception:
        return fallback


def clean_value(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() in {"none", "nan"}:
        return ""

    return value


def get_valid_status(status):
    status = clean_value(status)

    if status not in STATUSES:
        return "Applied"

    return status


def render_success_messages():
    if st.session_state.get("application_saved"):
        st.success("Application saved successfully.")
        st.session_state["application_saved"] = False

    if st.session_state.get("application_updated"):
        st.success("Application updated successfully.")
        st.session_state["application_updated"] = False

    if st.session_state.get("application_deleted"):
        st.success("Application deleted successfully.")
        st.session_state["application_deleted"] = False


def render_add_application_form():
    if not st.session_state.get("show_add_application_form"):
        render_pending_application_review()
        return

    with st.container(border=True):
        input_mode = st.radio(
            "How would you like to add it?",
            ["Job URL (recommended)", "Paste job description"],
            horizontal=True,
            key="application_input_mode",
        )
        with st.form("add_application_form", enter_to_submit=False):
            if input_mode == "Job URL (recommended)":
                source_url = st.text_input(
                    "Job posting URL",
                    placeholder="https://www.linkedin.com/jobs/view/...",
                    help="Use a public posting URL. Pages requiring login may need the paste fallback.",
                )
                job_description = ""
                submitted = st.form_submit_button("Read posting & continue", type="primary")
            else:
                job_description = st.text_area(
                    "Paste Job Description",
                    height=300,
                    placeholder="Tip: add 'Company: Company Name' at the top if the job ad does not clearly show the company.",
                )
                source_url = st.text_input("Job URL (optional)")
                submitted = st.form_submit_button("Analyze description & continue", type="primary")

            if submitted:
                try:
                    application_source = ""
                    if input_mode == "Job URL (recommended)":
                        if not source_url.strip():
                            st.error("Please enter the job posting URL first.")
                            return
                        with st.spinner("Reading the job posting…", show_time=True):
                            fetched_posting = fetch_job_posting(source_url)
                        job_description = fetched_posting["text"]
                        source_url = fetched_posting["url"]
                        application_source = application_source.strip() or fetched_posting["source_label"]
                    elif not job_description.strip():
                        st.error("Please paste the job description first.")
                        return

                    with st.spinner("Analyzing job posting…", show_time=True):
                        extracted_data = analyze_jd_with_openai(job_description)

                        if not extracted_data.get("job_title"):
                            st.error("Could not detect the job title. Please check the job description and try again.")
                            return
                        if input_mode == "Job URL (recommended)" and not any(
                            extracted_data.get(field)
                            for field in (
                                "technical_skills",
                                "tools_platforms",
                                "responsibilities",
                            )
                        ):
                            raise JobPageFetchError(
                                "The URL returned job metadata but not enough of the job-description body for skill extraction."
                            )

                    duplicate_df = get_duplicate_applications(
                        extracted_data.get("company", ""),
                        extracted_data.get("job_title", ""),
                        source_url,
                    )

                    st.session_state["pending_application"] = {
                        "job_description": job_description,
                        "extracted_data": extracted_data,
                        "intake_mode": "url" if input_mode == "Job URL (recommended)" else "paste",
                        "date_applied": date.today(),
                        "follow_up_date": add_business_days(date.today(), 5),
                        "contact_name": clean_value(extracted_data.get("recruiter_name")),
                        "contact_email": "",
                        "contact_role": "Recruiter" if clean_value(extracted_data.get("recruiter_name")) else "",
                        "contact_number": "",
                        "source_url": source_url,
                        "location": clean_value(extracted_data.get("location")),
                        "salary_range": clean_value(extracted_data.get("salary_range")),
                        "work_mode": clean_value(extracted_data.get("work_mode")) or "Not specified",
                        "application_source": application_source if input_mode == "Job URL (recommended)" else "",
                        "current_status": "Applied",
                        "notes": "",
                        "duplicates": duplicate_df.to_dict("records"),
                    }
                    st.session_state["show_add_application_form"] = False
                    st.rerun()

                except json.JSONDecodeError:
                    st.error("The AI response was not valid. Please try again.")
                except JobPageFetchError as error:
                    st.session_state["job_url_error"] = str(error)
                except Exception as error:
                    st.error(f"Something went wrong: {error}")

        url_error = st.session_state.pop("job_url_error", "")
        if url_error:
            st.error(url_error)
            st.info("This posting could not be read from its URL. Use the paste option instead.")
            if st.button("Switch to paste job description", key="switch_to_paste_after_url_error"):
                st.session_state["application_input_mode"] = "Paste job description"
                st.rerun()

    render_pending_application_review()


def render_pending_application_review():
    pending = st.session_state.get("pending_application")
    if not pending:
        return

    extracted = pending["extracted_data"]
    is_incomplete_url_review = (
        not pending.get("intake_mode")
        and "linkedin.com/jobs" in clean_value(pending.get("source_url")).lower()
        and not any(
            extracted.get(field)
            for field in (
                "technical_skills",
                "tools_platforms",
                "responsibilities",
            )
        )
    )
    if is_incomplete_url_review:
        st.error(
            "This incomplete review was created by an earlier LinkedIn URL read. "
            "It contains page metadata but not the job-description body."
        )
        st.info("Discard this result and retry the URL, or switch to the paste-JD option.")
        if st.button("Discard incomplete result and retry", key="discard_incomplete_url_review"):
            st.session_state.pop("pending_application", None)
            st.session_state["application_input_mode"] = "Job URL (recommended)"
            st.session_state["open_add_application"] = True
            st.rerun()
        return

    missing_job_details = not any(
        extracted.get(field)
        for field in (
            "technical_skills",
            "tools_platforms",
            "responsibilities",
        )
    )
    if missing_job_details and len(clean_value(pending.get("job_description"))) > 400:
        st.error("The previous analysis missed the job requirements in this description.")
        if st.button("Re-analyze full job description", key="retry_incomplete_jd_review", type="primary"):
            try:
                with st.spinner("Analyzing the complete job description…", show_time=True):
                    pending["extracted_data"] = analyze_jd_with_openai(
                        pending["job_description"], force_refresh=True
                    )
                st.session_state["pending_application"] = pending
                st.rerun()
            except Exception as error:
                st.error(f"Could not re-analyze the description: {error}")
        return

    st.subheader("Review application")

    recruiter_name = clean_value(extracted.get("recruiter_name"))
    parent_company = clean_value(extracted.get("parent_company"))
    end_client_name = clean_value(extracted.get("end_client_name"))
    end_client_industry = clean_value(extracted.get("end_client_industry"))
    if recruiter_name:
        client_label = end_client_name or end_client_industry or "undisclosed client"
        parent_label = f" ({parent_company})" if parent_company else ""
        st.info(
            f"Recruiter posting detected: {recruiter_name}{parent_label}. "
            f"Client: {client_label}."
        )
    extraction_warnings = build_extraction_warnings(
        extracted,
        pending["job_description"],
    )
    if extraction_warnings:
        with st.expander("Extraction checks", expanded=True):
            for warning in extraction_warnings:
                st.warning(warning)

    if pending.get("duplicates"):
        st.warning(
            "A similar application already exists. Review the details before saving: "
            + ", ".join(
                f"{item.get('company', '')} — {item.get('job_title', '')}"
                for item in pending["duplicates"]
            )
        )
    with st.container(border=True):
        with st.form("review_extracted_application", enter_to_submit=False):
            first_col, second_col = st.columns(2)
            with first_col:
                company = st.text_input(
                    "Company",
                    value=clean_value(extracted.get("company")),
                )
                job_title = st.text_input(
                    "Job title",
                    value=clean_value(extracted.get("job_title")),
                )
                domain = st.selectbox(
                    "Domain",
                    DOMAINS,
                    index=DOMAINS.index(extracted.get("domain"))
                    if extracted.get("domain") in DOMAINS
                    else DOMAINS.index("Other"),
                )
            with second_col:
                source_url = st.text_input("Job URL", value=pending.get("source_url", ""))
                application_source = st.text_input(
                    "Application source",
                    value=pending.get("application_source", ""),
                )
                location = st.text_input("Location", value=pending.get("location", ""))
                salary_range = st.text_input(
                    "Salary range",
                    value=pending.get("salary_range", ""),
                )

            technical_skills = st.text_area(
                "Technical skills",
                value="\n".join(extracted.get("technical_skills", [])),
                height=110,
            )
            tools_platforms = st.text_area(
                "Tools and platforms",
                value="\n".join(extracted.get("tools_platforms", [])),
                height=90,
            )
            certifications = st.text_area(
                "Certifications",
                value="\n".join(extracted.get("certifications", [])),
                height=90,
            )
            responsibilities = st.text_area(
                "Responsibilities",
                value="\n".join(extracted.get("responsibilities", [])),
                height=120,
            )

            with st.expander("Application tracking (optional)", expanded=False):
                metadata_col1, metadata_col2, metadata_col3, metadata_col4 = st.columns(4)
                with metadata_col1:
                    date_applied = st.date_input(
                        "Date applied",
                        value=parse_date_value(pending.get("date_applied"), fallback=date.today()),
                    )
                with metadata_col2:
                    stored_follow_up = parse_date_value(pending.get("follow_up_date"))
                    selected_follow_up = st.date_input(
                        "Follow-up date",
                        value=stored_follow_up or add_business_days(date_applied, 5),
                    )
                    no_follow_up = st.checkbox(
                        "No follow-up date",
                        value=stored_follow_up is None,
                        help="The date above will not be saved when this is checked.",
                    )
                    follow_up_date = "" if no_follow_up else selected_follow_up
                with metadata_col3:
                    current_status = st.selectbox(
                        "Status",
                        STATUSES,
                        index=STATUSES.index(pending.get("current_status", "Applied"))
                        if pending.get("current_status", "Applied") in STATUSES
                        else 0,
                        format_func=lambda status: STATUS_DISPLAY.get(status, status),
                    )
                with metadata_col4:
                    work_mode = st.selectbox(
                        "Work mode",
                        ["Not specified", "On-site", "Hybrid", "Remote"],
                        index=["Not specified", "On-site", "Hybrid", "Remote"].index(
                            pending.get("work_mode", "Not specified")
                        )
                        if pending.get("work_mode", "Not specified") in ["Not specified", "On-site", "Hybrid", "Remote"]
                        else 0,
                    )
                with st.container(border=True):
                    st.markdown("**Contact details**")
                    contact_col1, contact_col2 = st.columns(2)
                    with contact_col1:
                        contact_name = st.text_input(
                            "Contact name",
                            value=clean_value(pending.get("contact_name")),
                        )
                        contact_email = st.text_input(
                            "Contact email",
                            value=clean_value(pending.get("contact_email")),
                        )
                    with contact_col2:
                        contact_role = st.text_input(
                            "Contact role",
                            value=clean_value(pending.get("contact_role")),
                        )
                        contact_number = st.text_input(
                            "Contact phone",
                            value=clean_value(pending.get("contact_number")),
                        )
                notes = st.text_area(
                    "Notes",
                    value=clean_value(pending.get("notes")),
                )

            save_col, cancel_col = st.columns([1, 5])
            save_clicked = save_col.form_submit_button("Save application")
            cancel_clicked = cancel_col.form_submit_button("Discard review")

            if save_clicked:
                if not company.strip() or not job_title.strip():
                    st.error("Company and Job Title are required.")
                    return

                extracted["company"] = company.strip()
                extracted["job_title"] = job_title.strip()
                extracted["domain"] = domain
                extracted["technical_skills"] = parse_list_text(technical_skills)
                extracted["tools_platforms"] = parse_list_text(tools_platforms)
                extracted["certifications"] = parse_list_text(certifications)
                extracted["responsibilities"] = parse_list_text(responsibilities)

                try:
                    with st.spinner("Saving application…"):
                        save_analyzed_application(
                            extracted_data=extracted,
                            date_applied=date_applied,
                            follow_up_date=follow_up_date,
                            contact_name=contact_name,
                            contact_number=contact_number,
                            current_status=current_status,
                            notes=notes,
                            job_description=pending["job_description"],
                            contact_email=contact_email,
                            contact_role=contact_role,
                            source_url=source_url,
                            location=location,
                            salary_range=salary_range,
                            work_mode=work_mode,
                            application_source=application_source,
                        )
                    st.session_state.pop("pending_application", None)
                    st.session_state["show_add_application_form"] = False
                    st.session_state["application_saved"] = True
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not save application: {error}")

            if cancel_clicked:
                st.session_state.pop("pending_application", None)
                st.session_state["show_add_application_form"] = False
                st.rerun()

        if st.button("Re-analyze this description", key="reanalyze_pending_application"):
            try:
                with st.spinner("Re-analyzing job description…", show_time=True):
                    pending["extracted_data"] = analyze_jd_with_openai(
                        pending["job_description"],
                        force_refresh=True,
                    )
                st.session_state["pending_application"] = pending
                st.rerun()
            except Exception as error:
                st.error(f"Could not re-analyze the job description: {error}")


def render_application_profile(row):
    row_id = int(row["id"])

    selected_date_applied = parse_date_value(
        row["date_applied"],
        fallback=date.today()
    )

    selected_follow_up_date = parse_date_value(
        row["follow_up_date"],
        fallback=add_business_days(selected_date_applied, 5)
    )

    selected_domain = row["domain"] if row["domain"] in DOMAINS else "Other"
    selected_status = get_valid_status(row["current_status"])

    back_col, job_col = st.columns([1, 4])
    if back_col.button("← Applications", key="back_to_applications_list"):
        st.session_state["editing_application_id"] = None
        st.session_state["scroll_to_top"] = st.session_state.get("scroll_to_top", 0) + 1
        st.rerun()
    source_file = clean_value(row.get("source_file"))
    jobs_df = get_jobs_df() if source_file else pd.DataFrame()
    has_job = not jobs_df.empty and bool((jobs_df["source_file"] == source_file).any())
    if has_job and job_col.button("View job details", key=f"profile_job_{row_id}"):
        open_application_workspace(row)
    st.title(clean_value(row["job_title"]) or "Application")
    st.caption(f"{clean_value(row['company']) or 'Unknown company'} · Application #{row_id}")

    with st.form(f"edit_application_form_{row_id}", enter_to_submit=False):
        with st.container(border=True):
            st.subheader("Application details")
            identity_col1, identity_col2, identity_col3 = st.columns([1.1, 1.7, 1])
            company = identity_col1.text_input("Company", value=clean_value(row["company"]), key=f"edit_company_{row_id}")
            job_title = identity_col2.text_input("Job title", value=clean_value(row["job_title"]), key=f"edit_job_title_{row_id}")
            domain = identity_col3.selectbox(
                "Domain", DOMAINS, index=DOMAINS.index(selected_domain), key=f"edit_domain_{row_id}"
            )
            detail_col1, detail_col2 = st.columns(2)
            source_url = detail_col1.text_input("Job URL", value=clean_value(row.get("source_url")), key=f"edit_source_url_{row_id}")
            application_source = detail_col2.text_input(
                "Application source", value=clean_value(row.get("application_source")), key=f"edit_application_source_{row_id}"
            )
            location_col, mode_col = st.columns(2)
            location = location_col.text_input("Location", value=clean_value(row.get("location")), key=f"edit_location_{row_id}")
            work_modes = ["Not specified", "On-site", "Hybrid", "Remote"]
            stored_mode = clean_value(row.get("work_mode")) or "Not specified"
            work_mode = mode_col.selectbox(
                "Work mode", work_modes,
                index=work_modes.index(stored_mode) if stored_mode in work_modes else 0,
                key=f"edit_work_mode_{row_id}",
            )

        with st.container(border=True):
            st.subheader("Tracking")
            tracking_col1, tracking_col2, tracking_col3 = st.columns(3)
            date_applied = tracking_col1.date_input(
                "Date applied", value=selected_date_applied, key=f"edit_date_applied_{row_id}"
            )
            with tracking_col2:
                selected_follow_up = st.date_input(
                    "Follow-up date", value=selected_follow_up_date, key=f"edit_follow_up_date_{row_id}"
                )
                no_follow_up = st.checkbox(
                    "No follow-up date", value=not bool(clean_value(row["follow_up_date"])),
                    key=f"edit_no_follow_up_{row_id}"
                )
                follow_up_date = "" if no_follow_up else selected_follow_up
            current_status = tracking_col3.selectbox(
                "Status", STATUSES, index=STATUSES.index(selected_status), key=f"edit_status_{row_id}",
                format_func=lambda status: STATUS_DISPLAY.get(status, status),
            )
            notes = st.text_area("Notes", value=clean_value(row["notes"]), key=f"edit_notes_{row_id}")

        with st.container(border=True):
            st.subheader("Contact")
            contact_col1, contact_col2 = st.columns(2)
            contact_name = contact_col1.text_input("Contact name", value=clean_value(row["contact_name"]), key=f"edit_contact_name_{row_id}")
            contact_role = contact_col2.text_input("Contact role", value=clean_value(row.get("contact_role")), key=f"edit_contact_role_{row_id}")
            contact_email = contact_col1.text_input("Contact email", value=clean_value(row.get("contact_email")), key=f"edit_contact_email_{row_id}")
            contact_number = contact_col2.text_input("Contact phone", value=clean_value(row["contact_number"]), key=f"edit_contact_number_{row_id}")

        with st.container(border=True):
            st.subheader("Documents")
            document_col1, document_col2 = st.columns(2)
            resume_version = document_col1.text_input(
                "Resume version", value=clean_value(row.get("resume_version")), key=f"edit_resume_version_{row_id}"
            )
            cover_letter_options = ["Not started", "Drafted", "Submitted", "Not required"]
            stored_cover_letter = clean_value(row.get("cover_letter_status")) or "Not started"
            cover_letter_status = document_col2.selectbox(
                "Cover letter", cover_letter_options,
                index=cover_letter_options.index(stored_cover_letter) if stored_cover_letter in cover_letter_options else 0,
                key=f"edit_cover_letter_{row_id}",
            )

        with st.expander("Interview, offer & outcome", expanded=selected_status in {"Interview", "Offer", "Rejected", "Withdrawn"}):
            outcome_col1, outcome_col2 = st.columns(2)
            interview_stage = outcome_col1.text_input("Interview stage", value=clean_value(row.get("interview_stage")), key=f"edit_interview_stage_{row_id}")
            interview_date = outcome_col2.text_input(
                "Interview date", value=clean_value(row.get("interview_date")), key=f"edit_interview_date_{row_id}", placeholder="YYYY-MM-DD"
            )
            offer_amount = outcome_col1.text_input("Offer amount", value=clean_value(row.get("offer_amount")), key=f"edit_offer_amount_{row_id}")
            offer_date = outcome_col2.text_input(
                "Offer date", value=clean_value(row.get("offer_date")), key=f"edit_offer_date_{row_id}", placeholder="YYYY-MM-DD"
            )
            rejected_reason = st.text_input(
                "Rejection / withdrawal reason", value=clean_value(row.get("rejected_reason")), key=f"edit_rejected_reason_{row_id}"
            )

        update_col, cancel_col = st.columns([1, 5])

        update_submitted = update_col.form_submit_button("Save changes", type="primary")
        cancel_submitted = cancel_col.form_submit_button("Discard changes")

        if update_submitted:
            if not company.strip() or not job_title.strip():
                st.error("Company and Job Title are required.")
                return

            try:
                with st.spinner("Saving application changes…"):
                    update_application(
                        application_id=row_id,
                        company=company,
                        job_title=job_title,
                        domain=domain,
                        date_applied=date_applied,
                        follow_up_date=follow_up_date,
                        contact_name=contact_name,
                        contact_number=contact_number,
                        contact_email=contact_email,
                        contact_role=contact_role,
                        source_url=source_url,
                        location=location,
                        work_mode=work_mode,
                        application_source=application_source,
                        resume_version=resume_version,
                        cover_letter_status=cover_letter_status,
                        rejected_reason=rejected_reason,
                        interview_date=interview_date,
                        interview_stage=interview_stage,
                        offer_amount=offer_amount,
                        offer_date=offer_date,
                        current_status=current_status,
                        notes=notes,
                    )
            except Exception as error:
                st.error(f"Could not save changes: {error}")
                return

            st.session_state["application_updated"] = True
            st.rerun()

        if cancel_submitted:
            st.session_state["editing_application_id"] = None
            st.rerun()

    history_col1, history_col2 = st.columns(2)
    with history_col1:
        with st.expander("Status history", expanded=False):
            status_history = get_application_status_history_df(row_id)
            if status_history.empty:
                st.caption("No status history available.")
            else:
                st.dataframe(status_history, width="stretch", hide_index=True)
    with history_col2:
        with st.expander("Follow-up history", expanded=False):
            follow_up_history = get_follow_up_events_df(row_id)
            if follow_up_history.empty:
                st.caption("No follow-up history available.")
            else:
                st.dataframe(follow_up_history, width="stretch", hide_index=True)

    if st.session_state.get("pending_delete_id") == row_id:
        render_delete_confirmation(row)
    elif st.button("Delete application", key=f"profile_delete_{row_id}", type="tertiary", icon=":material/delete_outline:"):
        st.session_state["pending_delete_id"] = row_id
        st.rerun()


def render_delete_confirmation(row):
    row_id = int(row["id"])

    label = (
        f"{clean_value(row['company']) or 'No company'} - "
        f"{clean_value(row['job_title']) or 'No job title'}"
    )

    st.warning(f"Are you sure you want to delete: {label}?")

    confirm_col, cancel_col = st.columns([1, 5])

    if confirm_col.button("Yes, delete", key=f"confirm_delete_{row_id}"):
        try:
            with st.spinner("Deleting application…"):
                delete_application(row_id)
        except Exception as error:
            st.error(f"Could not delete application: {error}")
            return

        st.session_state["pending_delete_id"] = None
        st.session_state["editing_application_id"] = None
        st.session_state["selected_application_id"] = None
        st.session_state["application_deleted"] = True
        st.rerun()

    if cancel_col.button("Cancel", key=f"cancel_delete_{row_id}"):
        st.session_state["pending_delete_id"] = None
        st.rerun()



def open_application_workspace(row):
    jobs_df = get_jobs_df()
    source_file = clean_value(row.get("source_file"))
    matches = jobs_df[jobs_df["source_file"] == source_file] if source_file and not jobs_df.empty else pd.DataFrame()
    if matches.empty:
        st.session_state["editing_application_id"] = int(row["id"])
        st.session_state["scroll_to_top"] = st.session_state.get("scroll_to_top", 0) + 1
        st.rerun()
        return
    st.session_state["selected_application_id"] = int(row["id"])
    st.session_state.pop("editing_application_id", None)
    navigate_to("Applications", job_id=int(matches.iloc[0]["id"]))


def render_application_pipeline(applications_df):
    pipeline_statuses = ["Applied", "Interview", "Offer", "Other"]
    columns = st.columns(len(pipeline_statuses))
    for column, pipeline_status in zip(columns, pipeline_statuses):
        with column:
            if pipeline_status == "Other":
                rows = applications_df[~applications_df["current_status"].isin(["Applied", "Interview", "Offer"])]
            else:
                rows = applications_df[applications_df["current_status"] == pipeline_status]
            st.markdown(f"#### {pipeline_status}  ·  {len(rows)}")
            for _, row in rows.head(20).iterrows():
                row_id = int(row["id"])
                with st.container(border=True):
                    st.markdown(f"**{clean_value(row.get('job_title')) or 'Untitled role'}**")
                    st.caption(clean_value(row.get("company")) or "Unknown company")
                    fit_display = clean_value(row.get("fit_display"))
                    if fit_display:
                        st.caption(f"Resume fit · {fit_display}")
                    follow_up = clean_value(row.get("follow_up_date"))
                    if follow_up:
                        st.caption(f"Follow-up · {follow_up}")
                    if st.button("Open workspace", key=f"pipeline_open_{row_id}", width="stretch"):
                        open_application_workspace(row)
            if len(rows) > 20:
                st.caption(f"Showing 20 of {len(rows)}")



def render_applications():
    render_success_messages()
    if st.session_state.pop("open_add_application", False):
        st.session_state["show_add_application_form"] = True

    applications_df = get_applications_df()
    editing_id = st.session_state.get("editing_application_id")
    if editing_id is not None:
        selected = applications_df[applications_df["id"] == editing_id]
        if not selected.empty:
            render_application_profile(selected.iloc[0])
            return
        st.session_state["editing_application_id"] = None

    st.title("Applications")
    jobs_df = attach_fit_scores(
        get_jobs_df(),
        get_skill_demand_rows_df(),
        get_resume_profiles_df(),
    )
    opportunities_df = build_opportunities_df(jobs_df, applications_df)
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Opportunities", len(opportunities_df))
    metric_col2.metric("Applications", len(applications_df))
    metric_col3.metric("Not applied", int((opportunities_df["kind"] == "job").sum()))
    metric_col4.metric("80%+ matches", int((pd.to_numeric(jobs_df.get("fit_score", pd.Series(dtype=float)), errors="coerce") >= 80).sum()))

    action_col, _ = st.columns([1.5, 4])
    is_adding = bool(st.session_state.get("show_add_application_form"))
    if action_col.button(
        "Close form" if is_adding else "＋ Add application",
        key="applications_analyze_new",
        type="secondary" if is_adding else "primary",
        width="stretch",
    ):
        st.session_state["show_add_application_form"] = not is_adding
        st.rerun()

    render_add_application_form()
    render_opportunity_list(opportunities_df, applications_df)


def render_opportunity_list(opportunities_df, applications_df):
    heading_col, export_col = st.columns([5, 1], vertical_alignment="bottom")
    heading_col.subheader("Opportunities")

    view = st.segmented_control(
        "Show", ["All", "Applications", "Not applied"],
        default="All", key="opportunities_view",
    )
    search_col, domain_col, status_col = st.columns([2, 1, 1])
    search = search_col.text_input("Search", key="opportunities_search", placeholder="Company, title, domain, or notes")
    domains = ["All", *sorted(value for value in opportunities_df["domain"].unique() if clean_value(value))]
    domain = domain_col.selectbox("Domain", domains, key="opportunities_domain")
    statuses = ["All", *sorted(value for value in opportunities_df["current_status"].unique() if clean_value(value))]
    status = status_col.selectbox("Status", statuses, key="opportunities_status")
    filtered = filter_opportunities(opportunities_df, view, search, domain, status)

    signature = f"{view}|{search}|{domain}|{status}"
    if st.session_state.get("opportunities_filter_signature") != signature:
        st.session_state["opportunities_current_page"] = 1
        st.session_state["opportunities_table_reset"] = st.session_state.get("opportunities_table_reset", 0) + 1
        st.session_state["opportunities_filter_signature"] = signature

    if not filtered.empty:
        export_col.download_button(
            "Export CSV",
            data=filtered[["company", "job_title", "domain", "fit_display", "current_status", "date_applied", "follow_up_date"]].to_csv(index=False).encode("utf-8"),
            file_name="career_opportunities.csv", mime="text/csv",
            key="download_opportunities_csv", type="tertiary", icon=":material/download:",
        )

    if view != "Not applied" and not applications_df.empty:
        layout = st.segmented_control("Layout", ["List", "Pipeline"], default="List", key="opportunities_layout")
        if layout == "Pipeline":
            application_ids = set(filtered["application_id"].dropna().astype(int))
            render_application_pipeline(applications_df[applications_df["id"].isin(application_ids)])
            return

    st.caption(f"Showing {len(filtered)} of {len(opportunities_df)} opportunities · Select a row for details; select a heading to sort.")
    render_opportunities_table(filtered)
