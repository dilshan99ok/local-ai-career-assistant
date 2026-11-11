import streamlit as st

from App.app_utils.database import (
    get_applications_for_job_df,
    get_application_messages_df,
    get_job_detail_df,
    get_jobs_df,
    get_resume_profiles_df,
    get_resume_versions_df,
    get_skill_demand_rows_df,
    save_cover_letter_version,
    save_application_message,
    save_resume_version,
)
from Scripts.job_fit import attach_fit_scores
from App.app_utils.navigation import navigate_to
from Scripts.resume_export import build_resume_docx, safe_resume_filename
from Scripts.resume_profiles import choose_profile
from Scripts.tailoring import (
    generate_cover_letter,
    generate_follow_up_email,
    generate_resume_tailoring,
)


def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def clear_generated_documents():
    for key in (
        "resume_tailoring_output", "resume_tailoring_editor", "resume_tailoring_version_name",
        "resume_tailoring_mode_saved", "cover_letter_output", "cover_letter_editor",
        "follow_up_email_output", "follow_up_email_editor",
    ):
        st.session_state.pop(key, None)


def render_tailoring():
    st.title("Tailoring Studio")

    jobs_df = get_jobs_df()
    profiles_df = get_resume_profiles_df()
    jobs_df = attach_fit_scores(jobs_df, get_skill_demand_rows_df(), profiles_df)
    if jobs_df.empty:
        st.info("Analyze a job before opening the tailoring studio.")
        return
    if profiles_df.empty:
        st.info("Create a resume profile in Resume & Gaps before tailoring documents.")
        return

    job_options = {}
    for _, row in jobs_df.iterrows():
        label = (
            f"#{int(row['id'])} · {clean_value(row['company']) or 'Unknown company'} · "
            f"{clean_value(row['job_title']) or 'Untitled role'} · "
            f"Fit {clean_value(row.get('fit_display')) or '—'}"
        )
        job_options[label] = int(row["id"])

    preferred_job_id = st.session_state.get("tailoring_job_id")
    labels = list(job_options)
    default_index = 0
    if preferred_job_id in job_options.values():
        default_index = list(job_options.values()).index(preferred_job_id)
    selected_job_label = st.selectbox(
        "Target job",
        labels,
        index=default_index,
        key="tailoring_job_selector",
    )
    job_id = job_options[selected_job_label]
    st.session_state["tailoring_job_id"] = job_id

    job_df = get_job_detail_df(job_id)
    if job_df.empty:
        st.error("The selected job could not be loaded.")
        return
    job = job_df.iloc[0].to_dict()
    if not clean_value(job.get("raw_description")):
        st.warning("This older job does not have a stored original description, so tailoring is unavailable until it is re-added.")
        return

    with st.container(border=True):
        job_col, action_col = st.columns([4, 1.2])
        with job_col:
            st.subheader(clean_value(job.get("job_title")) or "Untitled role")
            st.caption(
                f"{clean_value(job.get('company')) or 'Unknown company'} · "
                f"{clean_value(job.get('domain')) or 'Unclassified'}"
            )
            selected_job_row = jobs_df[jobs_df["id"] == job_id]
            if not selected_job_row.empty:
                st.caption(f"Resume fit · {clean_value(selected_job_row.iloc[0].get('fit_display')) or '—'}")
        with action_col:
            if st.button("View workspace", key="tailoring_view_workspace", use_container_width=True):
                navigate_to("Jobs", job_id=int(job_id))

    if st.session_state.get("tailoring_source_job_id") != job_id:
        st.session_state.pop("tailoring_profile_selector", None)
        st.session_state.pop("tailoring_resume_version_selector", None)
        st.session_state.pop("saved_tailored_cv_selector", None)
        st.session_state["tailoring_source_job_id"] = job_id
        clear_generated_documents()

    recommended = choose_profile(profiles_df, clean_value(job.get("domain")))
    profile_options = {}
    for _, row in profiles_df.iterrows():
        label = (
            f"{clean_value(row['profile_name'])} · "
            f"{clean_value(row.get('target_domain')) or 'General'}"
        )
        if row["is_active"]:
            label += " · active"
        profile_options[label] = row
    profile_labels = list(profile_options)
    recommended_index = next(
        (index for index, label in enumerate(profile_labels)
         if int(profile_options[label]["id"]) == int(recommended["id"])),
        0,
    )
    selected_profile_label = st.selectbox(
        "Starting CV",
        profile_labels,
        index=recommended_index,
        key="tailoring_profile_selector",
    )
    profile = profile_options[selected_profile_label]
    profile_id = int(profile["id"])
    if st.session_state.get("tailoring_source_profile_id") != profile_id:
        st.session_state.pop("tailoring_resume_version_selector", None)
        st.session_state.pop("saved_tailored_cv_selector", None)
        st.session_state["tailoring_source_profile_id"] = profile_id
        clear_generated_documents()

    versions_df = get_resume_versions_df(profile_id=profile_id)
    version_options = {"Base CV": clean_value(profile.get("resume_text"))}
    for _, row in versions_df.iterrows():
        if (
            row["source_type"] == "tailored"
            and row["target_job_id"] == job_id
            and clean_value(row.get("change_summary")) != "Suggestions"
        ):
            version_options[f"#{int(row['id'])} · {row['version_name']}"] = row["content"]
    selected_version = st.selectbox(
        "Starting version",
        list(version_options),
        key="tailoring_resume_version_selector",
    )
    resume_text = version_options[selected_version]
    context = (job_id, profile_id, selected_version)
    if st.session_state.get("tailoring_generation_context") != context:
        clear_generated_documents()
        st.session_state["tailoring_generation_context"] = context
    if not resume_text:
        st.warning("The selected resume version is empty.")
        return

    applications_df = get_applications_for_job_df(job.get("source_file", ""))
    application_id = None
    if not applications_df.empty:
        application_options = {"No linked application": None}
        for _, row in applications_df.iterrows():
            label = f"#{int(row['id'])} · {row['current_status']} · {row['date_applied']}"
            application_options[label] = int(row["id"])
        selected_application = st.selectbox(
            "Link generated documents to application",
            list(application_options),
            key="tailoring_application_selector",
        )
        application_id = application_options[selected_application]

    resume_tab, cover_letter_tab, follow_up_tab = st.tabs(
        ["Resume", "Cover letter", "Follow-up"]
    )

    with resume_tab:
        mode = st.radio(
            "Output type",
            ["Suggestions", "Tailored draft"],
            horizontal=True,
            key="resume_tailoring_mode",
        )
        if st.button("Generate resume output", key="generate_resume_output"):
            try:
                with st.spinner("Preparing resume recommendations..."):
                    st.session_state["resume_tailoring_output"] = generate_resume_tailoring(
                        job,
                        resume_text,
                        mode,
                    )
                    st.session_state["resume_tailoring_mode_saved"] = mode
                    st.session_state["resume_tailoring_editor"] = st.session_state["resume_tailoring_output"]
                st.rerun()
            except Exception as error:
                st.error(f"Could not generate resume output: {error}")

        output = st.session_state.get("resume_tailoring_output", "")
        if output and mode != st.session_state.get("resume_tailoring_mode_saved"):
            st.info("Generate again after changing the output type.")
            output = ""
        if output:
            edited_output = st.text_area(
                "Review and edit resume output",
                value=output,
                height=520,
                key="resume_tailoring_editor",
            )
            version_name = st.text_input(
                "New resume version name",
                value=f"{job.get('job_title', 'Tailored resume')} draft",
                key="resume_tailoring_version_name",
            )
            if mode == "Tailored draft" and edited_output.strip():
                st.download_button(
                    "Download reviewed draft (.docx)",
                    data=build_resume_docx(edited_output),
                    file_name=safe_resume_filename(version_name),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_resume_tailoring_draft",
                )
            if st.button("Save resume version", key="save_resume_tailoring_version"):
                if not version_name.strip() or not edited_output.strip():
                    st.error("Add a version name and resume content before saving.")
                    return
                version_type = "tailored" if mode == "Tailored draft" else "suggestions"
                version_id = save_resume_version(
                    version_name=version_name,
                    content=edited_output,
                    profile_id=profile_id,
                    source_type=version_type,
                    target_job_id=job_id,
                    change_summary=st.session_state.get("resume_tailoring_mode_saved", "Suggestions"),
                    application_id=application_id if version_type == "tailored" else None,
                )
                st.success(f"Saved resume version #{version_id}.")
                st.session_state.pop("resume_tailoring_output", None)

        saved_for_job = get_resume_versions_df(profile_id=profile_id)
        saved_for_job = saved_for_job[
            (saved_for_job["target_job_id"] == job_id)
            & (saved_for_job["source_type"] == "tailored")
            & (saved_for_job["change_summary"].fillna("") != "Suggestions")
        ] if not saved_for_job.empty else saved_for_job
        if not saved_for_job.empty:
            st.markdown("#### Saved drafts for this job")
            draft_options = {
                f"#{int(row['id'])} · {row['version_name']} · {str(row['created_at'])[:16]}": row
                for _, row in saved_for_job.iterrows()
            }
            selected_draft = st.selectbox(
                "Saved tailored CV", list(draft_options), key="saved_tailored_cv_selector"
            )
            draft = draft_options[selected_draft]
            st.download_button(
                "Download saved CV (.docx)",
                data=build_resume_docx(draft["content"]),
                file_name=safe_resume_filename(draft["version_name"]),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_saved_tailored_cv",
            )

    with cover_letter_tab:
        tone = st.selectbox(
            "Tone",
            ["professional", "concise", "confident", "conversational"],
            key="cover_letter_tone",
        )
        length = st.selectbox(
            "Length",
            ["approximately 250 words", "approximately 350 words", "under 500 words"],
            key="cover_letter_length",
        )
        if st.button("Generate cover letter", key="generate_cover_letter"):
            try:
                with st.spinner("Preparing cover letter..."):
                    st.session_state["cover_letter_output"] = generate_cover_letter(
                        job,
                        resume_text,
                        tone,
                        length,
                    )
                st.rerun()
            except Exception as error:
                st.error(f"Could not generate cover letter: {error}")

        cover_output = st.session_state.get("cover_letter_output", "")
        if cover_output:
            edited_cover = st.text_area(
                "Review and edit cover letter",
                value=cover_output,
                height=460,
                key="cover_letter_editor",
            )
            cover_version_name = st.text_input(
                "Cover letter version name",
                value=f"{job.get('job_title', 'Cover letter')} letter",
                key="cover_letter_version_name",
            )
            cover_status = st.selectbox(
                "Cover letter status",
                ["Drafted", "Reviewed", "Submitted", "Not required"],
                key="cover_letter_status",
            )
            if st.button("Save cover letter version", key="save_cover_letter_version"):
                version_id = save_cover_letter_version(
                    version_name=cover_version_name,
                    content=edited_cover,
                    job_id=job_id,
                    application_id=application_id,
                    tone=tone,
                    status=cover_status,
                )
                st.success(f"Saved cover letter version #{version_id}.")
                st.session_state.pop("cover_letter_output", None)

    with follow_up_tab:
        st.caption("Generate a concise, truthful follow-up draft linked to this job and application.")
        application_context = applications_df.iloc[0].to_dict() if not applications_df.empty else {}
        if not application_context:
            st.info("Link an application to this job before generating a follow-up email.")
        elif st.button("Generate follow-up email", key="generate_follow_up_email"):
            try:
                with st.spinner("Preparing follow-up email..."):
                    st.session_state["follow_up_email_output"] = generate_follow_up_email(
                        job,
                        resume_text,
                        application_context,
                    )
                st.rerun()
            except Exception as error:
                st.error(f"Could not generate follow-up email: {error}")

        follow_up_output = st.session_state.get("follow_up_email_output", "")
        if follow_up_output:
            edited_follow_up = st.text_area(
                "Review and edit follow-up email",
                value=follow_up_output,
                height=320,
                key="follow_up_email_editor",
            )
            message_status = st.selectbox(
                "Message status",
                ["Drafted", "Reviewed", "Sent"],
                key="follow_up_message_status",
            )
            if st.button("Save follow-up email", key="save_follow_up_email"):
                message_id = save_application_message(
                    content=edited_follow_up,
                    job_id=job_id,
                    application_id=application_id,
                    status=message_status,
                )
                st.success(f"Saved follow-up email #{message_id}.")
                st.session_state.pop("follow_up_email_output", None)
