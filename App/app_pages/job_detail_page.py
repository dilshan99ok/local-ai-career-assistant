import ast
from html import escape

import pandas as pd
import streamlit as st

from App.app_utils.database import (
    get_applications_for_job_df,
    get_application_messages_df,
    get_cover_letter_versions_df,
    get_job_certifications_for_job_df,
    get_job_detail_df,
    get_job_skills_for_job_df,
    get_job_resume_recommendation,
    has_job_resume_recommendation,
    get_job_cv_checklist,
    get_resume_profiles_df,
    ensure_resume_extraction_reports,
    get_resume_versions_df,
    save_job_resume_recommendation,
    save_job_cv_checklist,
    update_application_status,
)
from Scripts.job_fit import build_fit_snapshot
from Scripts.ats_review import UNVERIFIED_SOURCE, checklist_guidance_hash
from Scripts.resume_recommendation import (
    build_edits, generate_job_checklist, generate_resume_recommendation,
    recommendation_fingerprint, required_criteria_summary, source_hash, validate_checklist,
)
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


def go_to_opportunities():
    go_back(fallback="Applications")


def go_to_tailoring(job_id, profile_id=None):
    st.session_state.pop("tailoring_profile_selector", None)
    if profile_id is not None:
        st.session_state["tailoring_requested_profile_id"] = int(profile_id)
    else:
        st.session_state.pop("tailoring_requested_profile_id", None)
    navigate_to("Tailoring Studio", job_id=int(job_id))


def render_fit_metric(fit):
    score = fit["score"]
    if score is None:
        st.metric("Skill coverage", "Unavailable", help="No job skills were extracted, or no CV is available.")
    else:
        st.metric("Skill coverage", f"{score}%", help="Share of extracted job skills found in the selected CV. This is not a hiring probability.")


def required_fit_header_value(recommendation, checklist):
    """Summarize the leading review without requesting another assessment."""
    if not recommendation or not checklist:
        return "Not assessed", "Analyze the CV pool to review required job criteria."
    review_id = recommendation.get("selected_profile_id")
    if review_id is None and recommendation.get("tied_profile_ids"):
        review_id = recommendation["tied_profile_ids"][0]
    review = next(
        (item for item in recommendation.get("cv_reviews", []) if item["profile_id"] == review_id), None
    )
    if review is None:
        return "Review incomplete", "No complete CV review is available."
    summary = required_criteria_summary(review, checklist["criteria"])
    if not summary["total"]:
        return "None specified", "The job checklist has no required criteria."
    detail = f"{summary['demonstrated']} of {summary['total']} required criteria demonstrated"
    if summary["unable"]:
        return "Review incomplete", f"{detail}; {len(summary['unable'])} unable to assess."
    if recommendation.get("provisional"):
        detail += ". Pool recommendation is provisional because another CV review is incomplete"
    return f"{summary['percentage']}%", detail


def render_job_header(job, job_id, applications_df, fit, recommendation, checklist):
    if not st.session_state.get("navigation_history"):
        if st.button("← Applications", key="back_to_jobs"):
            go_to_opportunities()

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

    applications_label = "No application record"
    follow_up = "—"
    if not applications_df.empty:
        application = applications_df.iloc[0]
        applications_label = STATUS_LABELS.get(
            clean_value(application.get("current_status")),
            clean_value(application.get("current_status")) or "Unknown",
        )
        follow_up = clean_value(application.get("follow_up_date")) or "—"

    action_col1, action_col2, action_col3 = st.columns(3)
    if action_col1.button("Tailor application", key=f"workspace_tailor_{job_id}", width="stretch"):
        go_to_tailoring(job_id)
    if action_col2.button("Edit application" if not applications_df.empty else "Add application", key=f"workspace_application_{job_id}", width="stretch"):
        if applications_df.empty:
            st.session_state["open_add_application"] = True
        else:
            st.session_state["editing_application_id"] = int(applications_df.iloc[0]["id"])
        navigate_to("Applications")
    source_url = clean_value(job.get("source_url"))
    if source_url:
        action_col3.link_button("Open original posting", source_url, width="stretch")

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    with metric_col1:
        required_value, required_help = required_fit_header_value(recommendation, checklist)
        st.metric("Required criteria fit", required_value, help=required_help)
    with metric_col2:
        render_fit_metric(fit)
    metric_col3.metric("Application", applications_label)
    metric_col4.metric("Follow-up", follow_up)


def render_overview_tab(job, skills_df):
    left, right = st.columns([1, 2], gap="large")
    with left:
        st.subheader("At a glance")
        snapshot = {
            "Location": clean_value(job.get("location")),
            "Work mode": clean_value(job.get("work_mode")),
            "Salary": clean_value(job.get("salary_range")),
            "Source": clean_value(job.get("application_source")),
        }
        for label, value in snapshot.items():
            if value and value != "Not specified":
                st.markdown(f"**{label}**  \n{value}")
        analyzed = (clean_value(job.get("analyzed_at")) or clean_value(job.get("created_at")))[:10]
        if analyzed:
            st.caption(f"Analyzed {analyzed}")

    with right:
        st.subheader("Skills in the posting")
        if skills_df.empty:
            st.info("No structured skills were extracted for this role.")
        else:
            skills = canonicalize_skill_rows(skills_df)
            for basket, group in skills.groupby("skill_basket", sort=False):
                names = group["canonical_skill"].dropna().drop_duplicates().tolist()
                with st.container(border=True):
                    st.markdown(f"**{basket}**")
                    st.write(" · ".join(names))

    raw_description = clean_value(job.get("raw_description"))
    with st.expander("View original job description", expanded=False):
        if raw_description:
            st.text_area("Original job description", value=raw_description, height=460, disabled=True, label_visibility="collapsed")
        else:
            st.warning("The original job description was not retained for this older record.")


def _checklist_alternatives(value):
    if isinstance(value, list):
        return ", ".join(map(str, value))
    value = clean_value(value)
    if value.startswith("["):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return ", ".join(map(str, parsed))
        except (ValueError, SyntaxError):
            pass
    return value


def _render_checklist_cards(criteria):
    for kind in ("Required", "Preferred", "Screening"):
        items = [item for item in criteria if item["kind"] == kind]
        if not items:
            continue
        st.markdown(f"**{kind}** · {len(items)}")
        cards = []
        for item in items:
            level = clean_value(item.get("requested_level"))
            alternatives = _checklist_alternatives(item.get("alternatives"))
            context = " · ".join(part for part in (level, f"Alternatives: {alternatives}" if alternatives else "") if part)
            context_html = f'<div class="job-checklist-context">{escape(context)}</div>' if context else ""
            cards.append(
                f'<div class="job-checklist-card {kind.lower()}">'
                f'<div class="job-checklist-type">{kind}</div>'
                f'<strong>{escape(clean_value(item.get("criterion")))}</strong>'
                f'{context_html}<div class="job-checklist-source">Job ad: {escape(clean_value(item.get("source")))}</div>'
                '</div>'
            )
        st.markdown('<div class="job-checklist-grid">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def _save_checklist_and_refresh(job, job_id, current, rows, profiles_df=None, rankings=None, had_review=False):
    changed = current is None or rows != current["criteria"]
    if not changed:
        if current.get("guidance_hash") != checklist_guidance_hash():
            save_job_cv_checklist(job_id, source_hash(job), rows, checklist_guidance_hash())
        return
    save_job_cv_checklist(job_id, source_hash(job), rows, checklist_guidance_hash())
    if had_review and profiles_df is not None and not profiles_df.empty:
        updated = get_job_cv_checklist(job_id)
        with st.spinner("Refreshing CV review for the updated checklist…", show_time=True):
            result = generate_resume_recommendation(job, profiles_df, rankings, updated)
            key = recommendation_fingerprint(job, profiles_df, updated, rankings)
            save_job_resume_recommendation(job_id, key, result)


def render_job_checklist(job, job_id, checklist, profiles_df=None, rankings=None, had_review=False):
    st.subheader("Job checklist")
    if checklist is None:
        st.info("Prepare a checklist from the saved job description, then review it before comparing CVs.")
        if st.button("Prepare job checklist", key=f"prepare_checklist_{job_id}", type="primary"):
            try:
                with st.spinner("Reading job requirements…", show_time=True):
                    rows = generate_job_checklist(job)
                    _save_checklist_and_refresh(job, job_id, checklist, rows, profiles_df, rankings, had_review)
                st.rerun()
            except (RuntimeError, ValueError) as error:
                st.error(f"Checklist could not be prepared: {error}")
        return None

    criteria = checklist["criteria"]
    if checklist.get("guidance_hash") != checklist_guidance_hash():
        st.info("This checklist was saved under older or unrecorded AI guidance. Review it or regenerate it to use the current rules.")
        if st.button("Regenerate checklist", key=f"regenerate_checklist_{job_id}"):
            try:
                with st.spinner("Reading job requirements…", show_time=True):
                    rows = generate_job_checklist(job)
                    _save_checklist_and_refresh(job, job_id, checklist, rows, profiles_df, rankings, had_review)
                st.rerun()
            except (RuntimeError, ValueError) as error:
                st.error(f"Checklist could not be prepared: {error}")
    _render_checklist_cards(criteria)
    with st.expander("Edit checklist", expanded=False):
        st.caption("Saving changed criteria refreshes the CV review. Viewing or saving unchanged criteria keeps the current result.")
        editor = st.data_editor(
            pd.DataFrame(criteria, columns=["id", "kind", "criterion", "source", "requested_level", "alternatives"]),
            key=f"job_checklist_editor_{job_id}_{checklist['version']}",
            hide_index=True, num_rows="dynamic", width="stretch",
            disabled=["id"],
            column_config={
                "id": None,
                "kind": st.column_config.SelectboxColumn("Type", options=["Required", "Preferred", "Screening"], required=True),
                "criterion": "Criterion", "source": "Source wording",
                "requested_level": "Requested level", "alternatives": "Alternatives",
            },
        )
        if st.button("Save checklist", key=f"save_checklist_{job_id}"):
            try:
                rows = editor.fillna("").to_dict("records")
                rows = [row for row in rows if row["criterion"] or row["source"]]
                validated = validate_checklist(rows, clean_value(job.get("raw_description")))
                if not validated:
                    raise ValueError("Add at least one criterion before saving.")
                _save_checklist_and_refresh(job, job_id, checklist, validated, profiles_df, rankings, had_review)
                st.rerun()
            except (RuntimeError, ValueError) as error:
                st.error(str(error))
    return checklist


def render_fit_tab(job, job_id, fit, profiles_df, fingerprint, checklist, recommendation):
    st.subheader("CV screening preview")
    st.caption("Based on the visible job ad and saved CV text; this does not predict an employer's decision.")
    if profiles_df.empty:
        st.info("Upload a CV in Resumes to compare it with this role.")
        if st.button("Open Resumes", key="open_resume_from_fit"):
            navigate_to("Resume & Gaps")
        return

    rankings = fit["rankings"]
    if checklist is None or not checklist["criteria"]:
        render_cv_comparison(rankings, recommendation, checklist["criteria"] if checklist else [])
        render_job_checklist(job, job_id, checklist)
        return

    if st.button(
        "Reanalyze CV pool" if recommendation else "Analyze CV pool",
        key=f"analyze_cv_pool_{job_id}", type="secondary" if recommendation else "primary",
        help="Sends the job checklist and extracted text from every CV to OpenAI in reviewable sections.",
    ):
        try:
            with st.spinner("Reviewing every CV section…", show_time=True):
                result = generate_resume_recommendation(job, profiles_df, rankings, checklist)
                save_job_resume_recommendation(job_id, fingerprint, result)
            st.rerun()
        except (RuntimeError, ValueError) as error:
            st.error(f"CV review could not be completed: {error}")

    if recommendation:
        render_review_outcome(recommendation, profiles_df)
    render_cv_comparison(rankings, recommendation, checklist["criteria"])
    render_job_checklist(job, job_id, checklist, profiles_df=profiles_df,
                         rankings=rankings,
                         had_review=bool(recommendation) or has_job_resume_recommendation(job_id))

    if recommendation:
        render_screening_result(job_id, profiles_df, checklist["criteria"], recommendation, fit["requested"])
    else:
        with st.expander("Skill coverage details"):
            render_skill_evidence(fit, show_heading=False)

def render_review_outcome(result, profiles_df):
    selected_id = result.get("selected_profile_id")
    names = {int(row["id"]): clean_value(row["profile_name"]) for _, row in profiles_df.iterrows()}
    if selected_id:
        label = "Recommended starting CV"
        outcome = names.get(int(selected_id), "CV")
        tone = "recommended"
        detail = "Required evidence leads the comparison; preferred evidence breaks close results."
    elif result.get("tied_profile_ids"):
        label = "No clear leader"
        outcome = "Evidence tie"
        tone = "tied"
        detail = "Required and preferred evidence do not distinguish these CVs."
    else:
        label = "CV pool review"
        outcome = "Recommendation pending"
        tone = "incomplete"
        detail = "No CV has a complete review yet."
    st.markdown(
        f'<div class="job-screening-outcome {tone}">'
        f'<span>{escape(label)}</span><strong>{escape(outcome)}</strong>'
        f'<p>{escape(detail)}</p></div>', unsafe_allow_html=True,
    )
    with st.expander("Why this result?"):
        st.write(result["reason"])
    if result.get("tied_profile_ids"):
        st.caption("Tied CVs: " + ", ".join(names.get(int(i), str(i)) for i in result["tied_profile_ids"]))
    if result.get("provisional"):
        st.warning("Provisional: incomplete review for " + ", ".join(result["incomplete_profiles"]) + ".")


def render_screening_result(job_id, profiles_df, criteria, result, job_skills_df=None):
    st.subheader("Evidence breakdown")
    selected_id = result.get("selected_profile_id")
    names = {int(row["id"]): clean_value(row["profile_name"]) for _, row in profiles_df.iterrows()}
    reviews = result["cv_reviews"]
    review_ids = [item["profile_id"] for item in reviews]
    chosen = st.selectbox("Inspect CV review", review_ids,
                          format_func=lambda value: names.get(value, str(value)),
                          index=review_ids.index(selected_id) if selected_id in review_ids else 0,
                          key=f"screening_review_cv_{job_id}")
    review = next(item for item in reviews if item["profile_id"] == chosen)
    st.caption("All saved CV text reviewed" if review["complete"] else "Review incomplete")
    if review["extraction_issues"]:
        st.warning("Extraction: " + " · ".join(review["extraction_issues"]))
    if review.get("validation_issues"):
        st.warning("Some AI evidence could not be verified: " + " · ".join(review["validation_issues"]))
    if review["omitted_sections"]:
        st.warning(f"{len(review['omitted_sections'])} section(s) not reviewed because of the request size limit.")
    with st.expander(f"Review scope and source · {len(review['reviewed_sections'])} sections reviewed, "
                     f"{len(review['omitted_sections'])} omitted"):
        if review.get("extraction_warnings"):
            if UNVERIFIED_SOURCE in review["extraction_warnings"]:
                st.caption("The original file is not attached. Screening used the saved extracted CV text.")
            other_warnings = [warning for warning in review["extraction_warnings"]
                              if warning != UNVERIFIED_SOURCE]
            if other_warnings:
                st.caption(" · ".join(other_warnings))
        profile = profiles_df[profiles_df["id"] == chosen].iloc[0]
        for section in review["reviewed_sections"]:
            st.caption(f"Reviewed {section['id']}: characters {section['start'] + 1}–{section['end']} · {section['label']}")
        for section in review["omitted_sections"]:
            st.caption(f"Not reviewed {section['id']}: characters {section['start'] + 1}–{section['end']} · {section['label']}")
        st.text_area("Saved extracted CV text", value=clean_value(profile.get("resume_text")),
                     height=320, disabled=True, key=f"screening_cv_text_{job_id}_{chosen}")

    by_id = {item["criterion_id"]: item for item in review["assessments"]}
    for kind in ("Required", "Preferred", "Screening"):
        kind_criteria = [item for item in criteria if item["kind"] == kind]
        if kind_criteria:
            st.markdown(f"#### {kind} criteria" if kind != "Screening" else "#### Screening conditions")
        for start in range(0, len(kind_criteria), 2):
            for column, criterion in zip(st.columns(2, gap="medium"), kind_criteria[start:start + 2]):
                item = by_id[criterion["id"]]
                status = item["status"]
                if kind == "Screening" and status != "Demonstrated":
                    status = "Not met" if item["issue_type"] == "unmet requirement" else "Confirm · " + status
                tone = ("confirm" if status.startswith("Confirm") else {
                    "Demonstrated": "demonstrated", "Partially demonstrated": "partial",
                    "Not shown": "missing", "Unable to assess": "unknown", "Not met": "missing",
                }.get(status, "unknown"))
                with column:
                    with st.container(border=True):
                        st.markdown(
                            '<div class="job-criterion-head">'
                            f'<strong>{escape(criterion["criterion"])}</strong>'
                            f'<span class="job-criterion-status {tone}">{escape(status)}</span>'
                            '</div>', unsafe_allow_html=True,
                        )
                        if criterion["source"].strip() != criterion["criterion"].strip():
                            st.caption(f"Job ad: {criterion['source']}")
                        reason = clean_value(item.get("reason"))
                        evidence = clean_value(item.get("evidence"))
                        if reason and (not evidence or reason.casefold() not in evidence.casefold()):
                            st.caption(reason)
                        if evidence:
                            st.markdown(f"**CV evidence:** {escape(evidence)}")

    if review.get("complete"):
        edits = build_edits(review, criteria)
        st.markdown("#### Prepare this CV")
        if edits:
            st.caption(f"{len(edits)} priority item(s) need clarification or stronger evidence. "
                       "Demonstrated criteria can also be brought forward in the tailored version.")
            for edit in edits:
                st.markdown(f"**{edit['kind']}: {edit['criterion']}** · {edit['edit_section']}")
        else:
            st.caption("No partial or missing criteria found. Tailoring can bring the strongest evidence forward.")
        if st.button("Open in Tailoring Studio", key=f"create_tailored_from_pick_{job_id}", type="primary"):
            go_to_tailoring(job_id, chosen)
    if job_skills_df is not None:
        selected_fit = build_fit_snapshot(job_skills_df, profiles_df, profile_id=chosen)
        with st.expander("Skill coverage details"):
            render_skill_evidence(selected_fit, show_heading=False)


def render_required_criteria_summary(review, criteria):
    summary = required_criteria_summary(review, criteria)
    if not summary["total"]:
        value = "None specified"
        count = ""
    elif summary["unable"]:
        value = "Review incomplete"
        count = f"{summary['demonstrated']} of {summary['total']} demonstrated · {len(summary['unable'])} unable to assess"
    else:
        value = f"{summary['percentage']}%"
        count = f"{summary['demonstrated']} of {summary['total']} demonstrated"
    tone = ("unknown" if summary["unable"] else "none" if not summary["total"] else
            "full" if summary["demonstrated"] == summary["total"] else "partial")
    progress = ""
    if summary["total"] and not summary["unable"]:
        full_width = summary["demonstrated"] / summary["total"] * 100
        partial_width = len(summary["partial"]) / summary["total"] * 100
        progress = ('<div class="job-cv-required-bar" aria-hidden="true">'
                    f'<span class="full" style="width:{full_width:.1f}%"></span>'
                    f'<span class="partial" style="width:{partial_width:.1f}%"></span></div>')
    details = "".join(
        f'<div class="job-cv-required-detail"><strong>{label}:</strong> '
        f'{escape(", ".join(summary[key]))}</div>'
        for key, label in (("partial", "Partial"), ("missing", "Not shown"),
                           ("unable", "Unable to assess")) if summary[key]
    )
    return (
        f'<div class="job-cv-required {tone}">'
        '<div class="job-cv-required-heading">Required criteria demonstrated</div>'
        f'<div class="job-cv-required-value">{value}</div>'
        f'<div class="job-cv-count">{count}</div>{progress}{details}</div>'
    )


def render_cv_comparison(rankings, recommendation, criteria):
    st.subheader("Compare CVs")
    selected_id = recommendation["selected_profile_id"] if recommendation else None
    tied_ids = set(recommendation.get("tied_profile_ids", [])) if recommendation else set()
    reviews = {int(review["profile_id"]): review for review in recommendation["cv_reviews"]} if recommendation else {}
    cards = []
    for _, row in rankings.iterrows():
        profile_id = int(row["profile_id"])
        recommended = selected_id is not None and profile_id == int(selected_id)
        score = int(row["score"]) if pd.notna(row["score"]) else None
        name = escape(clean_value(row["profile_name"]) or "Untitled CV")
        category = escape(clean_value(row["target_domain"]) or "General")
        badge = ('<span class="job-cv-pick">Recommended</span>' if recommended else
                 '<span class="job-cv-pick">Tied</span>' if profile_id in tied_ids else "")
        if score is None:
            score_html = '<span class="job-cv-score-empty">Skill coverage unavailable</span>'
            bar = ""
        else:
            matched = int(row["matched"])
            requested = int(row["requested"])
            score_html = f'<span class="job-cv-score-label">Skill coverage</span><strong class="job-cv-score">{score}%</strong>'
            bar = (
                f'<div class="job-cv-bar" role="progressbar" aria-label="{name} skill coverage" '
                f'aria-valuenow="{score}" aria-valuemin="0" aria-valuemax="100">'
                f'<span style="width: {score}%"></span></div>'
                f'<div class="job-cv-count">{matched} of {requested} job skills detected</div>'
            )
        required = render_required_criteria_summary(reviews[profile_id], criteria) if profile_id in reviews else ""
        cards.append(
            f'<div class="job-cv-card{" recommended" if recommended else ""}{" pending" if not recommendation else ""}">'
            f'<div class="job-cv-top"><div><div class="job-cv-name">{name}{badge}</div>'
            f'<div class="job-cv-category">{category}</div></div></div>'
            f'{required}<div class="job-cv-skill-summary">'
            f'<div class="job-cv-score-wrap">{score_html}</div>{bar}</div></div>'
        )
    st.markdown('<div class="job-cv-comparison">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_skill_evidence(fit, show_heading=True):
    if show_heading:
        st.subheader("Skill evidence")
    if fit.get("profile_name"):
        st.caption(f"Detected in {fit['profile_name']}")
    matched = fit["matched"].get("canonical_skill", pd.Series(dtype=str)).dropna().drop_duplicates().tolist()
    missing = fit["missing"].get("canonical_skill", pd.Series(dtype=str)).dropna().drop_duplicates().tolist()
    if not matched and not missing:
        st.info("No extracted skills to compare yet.")
        return

    def panel(title, skills, tone):
        chips = "".join(f'<span class="job-skill-chip">{escape(str(skill))}</span>' for skill in skills)
        if not chips:
            chips = '<span class="job-skill-empty">None detected</span>'
        return (
            f'<div class="job-skill-panel {tone}"><div class="job-skill-heading">'
            f'<span>{title}</span><strong>{len(skills)}</strong></div>'
            f'<div class="job-skill-chips">{chips}</div></div>'
        )

    st.markdown(
        '<div class="job-skill-evidence">'
        + panel("Found in selected CV", matched, "found")
        + panel("Not detected in selected CV", missing, "missing")
        + "</div>",
        unsafe_allow_html=True,
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
                    with st.spinner("Updating application status…"):
                        update_application_status(int(application["id"]), selected_status)
                    st.rerun()
            if st.button("Edit application", key=f"workspace_edit_application_{int(application['id'])}"):
                st.session_state["editing_application_id"] = int(application["id"])
                navigate_to("Applications")


def render_job_detail():
    job_id = st.session_state.get("selected_job_id")
    if not job_id:
        st.info("Select an opportunity to view its details.")
        if st.button("Go to Applications"):
            go_to_opportunities()
        return

    job_df = get_job_detail_df(job_id)
    if job_df.empty:
        st.error("This job could not be found.")
        if st.button("Back to Applications"):
            go_to_opportunities()
        return

    job = job_df.iloc[0].to_dict()
    skills_df = get_job_skills_for_job_df(job_id)
    certs_df = get_job_certifications_for_job_df(job_id)
    applications_df = get_applications_for_job_df(job_id)
    selected_application_id = st.session_state.get("selected_application_id")
    if selected_application_id is not None and not applications_df.empty:
        selected = applications_df[applications_df["id"] == selected_application_id]
        if not selected.empty:
            applications_df = pd.concat(
                [selected, applications_df[applications_df["id"] != selected_application_id]],
                ignore_index=True,
            )
    ensure_resume_extraction_reports()
    profiles_df = get_resume_profiles_df()
    checklist = get_job_cv_checklist(job_id)
    if checklist and checklist["source_hash"] != source_hash(job):
        checklist = None
    initial_fit = build_fit_snapshot(skills_df, profiles_df, job.get("domain", ""))
    fingerprint = recommendation_fingerprint(job, profiles_df, checklist, initial_fit["rankings"])
    recommendation = get_job_resume_recommendation(job_id, fingerprint) if not profiles_df.empty else None
    if recommendation is None and checklist and not profiles_df.empty:
        legacy_key = recommendation_fingerprint(
            job, profiles_df, checklist, initial_fit["rankings"], include_checklist_metadata=True,
        )
        recommendation = get_job_resume_recommendation(job_id, legacy_key)
        if recommendation is not None:
            save_job_resume_recommendation(job_id, fingerprint, recommendation)
    leading_profile_id = None
    if recommendation:
        leading_profile_id = recommendation.get("selected_profile_id")
        if leading_profile_id is None and recommendation.get("tied_profile_ids"):
            leading_profile_id = recommendation["tied_profile_ids"][0]
    fit = build_fit_snapshot(
        skills_df, profiles_df, job.get("domain", ""),
        profile_id=leading_profile_id,
    )

    render_job_header(job, job_id, applications_df, fit, recommendation, checklist)
    section = st.segmented_control(
        "Job section", ["Overview", "Fit & gaps", "Application packet", "Tracking"],
        default="Overview", required=True, key=f"job_detail_section_{job_id}",
        label_visibility="collapsed",
    )

    if section == "Overview":
        render_overview_tab(job, skills_df)
        st.subheader("Certifications")
        if certs_df.empty:
            st.info("No certifications were extracted for this role.")
        else:
            st.dataframe(build_certification_summary(certs_df), width="stretch", hide_index=True)
    elif section == "Fit & gaps":
        render_fit_tab(job, job_id, fit, profiles_df, fingerprint, checklist, recommendation)
    elif section == "Application packet":
        render_packet_tab(job_id, applications_df)
    else:
        render_tracking_tab(applications_df)
