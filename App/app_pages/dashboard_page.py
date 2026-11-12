from datetime import date
from html import escape

import altair as alt
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from App.app_utils.database import (
    clear_application_follow_up,
    extend_application_follow_up,
    get_application_trend_df,
    get_dashboard_followups_df,
    get_domains_df,
    get_jobs_df,
    get_resume_profiles_df,
    get_skill_demand_rows_df,
    get_status_summary_df,
    get_top_skill_areas_df,
    get_applications_df,
)
from Scripts.job_fit import attach_fit_scores, build_job_fit_summary
from App.app_utils.navigation import navigate_to


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


def go_to(page):
    navigate_to(page)


def open_job_workspace(job_id):
    if job_id is None or clean_value(job_id) == "":
        return
    navigate_to("Jobs", job_id=int(job_id))


def followup_state(value):
    try:
        target = date.fromisoformat(clean_value(value))
    except ValueError:
        return clean_value(value) or "—", "normal"
    if target < date.today():
        return f"Overdue · {target}", "overdue"
    if target == date.today():
        return f"Today · {target}", "today"
    return str(target), "normal"


def render_header(jobs_df, applications_df, fit_summary):
    st.title("Your career workspace")

    active = applications_df[
        ~applications_df["current_status"].isin(["Rejected", "Withdrawn", "Archived"])
    ] if not applications_df.empty else applications_df
    interviews = len(applications_df[applications_df["current_status"] == "Interview"]) if not applications_df.empty else 0
    offers = len(applications_df[applications_df["current_status"] == "Offer"]) if not applications_df.empty else 0
    followups = len(get_dashboard_followups_df())
    fit_scores = pd.to_numeric(fit_summary.get("fit_score", pd.Series(dtype=float)), errors="coerce")
    strong_matches = int((fit_scores >= 80).sum()) if not fit_summary.empty else 0

    cols = st.columns(5)
    cols[0].metric("Active applications", len(active))
    cols[1].metric(
        "80%+ job matches",
        strong_matches,
        help="Jobs where at least 80% of extracted skills appear in the matching category CV, or the default CV when no category matches.",
    )
    cols[2].metric("Interviews", interviews)
    cols[3].metric("Offers", offers)
    cols[4].metric("Next follow-ups", followups)


def render_quick_actions():
    st.subheader("Quick actions")
    col1, col2, col3 = st.columns(3)
    if col1.button("＋ Add application", key="overview_analyze_job", type="primary", width="stretch"):
        st.session_state["open_add_application"] = True
        go_to("Applications")
    if col2.button("View job library", key="overview_view_jobs", width="stretch"):
        go_to("Jobs")
    if col3.button("Review resume gaps", key="overview_review_gaps", width="stretch"):
        go_to("Resume & Gaps")


def render_next_actions(followups_df, fit_summary):
    st.subheader("Next actions")
    if followups_df.empty:
        st.success("No follow-ups are currently due. Your queue is clear.")
        return

    with st.container(border=True):
        for index, (_, row) in enumerate(followups_df.head(6).iterrows()):
            application_id = int(row["id"])
            label, state = followup_state(row.get("follow_up_date"))
            job_id_value = clean_value(row.get("job_id"))
            try:
                job_id = int(float(job_id_value)) if job_id_value else None
            except (TypeError, ValueError):
                job_id = None
            fit_row = None
            if job_id is not None and not fit_summary.empty:
                matches = fit_summary[fit_summary["job_id"] == job_id]
                fit_row = matches.iloc[0] if not matches.empty else None
            if index:
                st.markdown('<div class="overview-row-divider"></div>', unsafe_allow_html=True)
            col1, col2, col3, actions = st.columns([2.35, 2.1, 1.55, 1.45])
            with col1:
                if job_id:
                    if st.button(
                        clean_value(row.get("job_title")) or "Untitled role",
                        key=f"overview_open_followup_{application_id}",
                        type="tertiary",
                        width="stretch",
                    ):
                        open_job_workspace(job_id)
                else:
                    st.markdown(
                        f'<div class="overview-action-title">{escape(clean_value(row.get("job_title")) or "Untitled role")}</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f'<div class="overview-action-meta">{escape(clean_value(row.get("company")) or "Unknown company")}</div>',
                    unsafe_allow_html=True,
                )
            col2.markdown(
                f'<div class="overview-state {state}">{escape(label)}</div>'
                f'<div class="overview-action-meta">{escape(clean_value(row.get("contact_name")) or "No contact recorded")}</div>',
                unsafe_allow_html=True,
            )
            fit_display = clean_value(fit_row.get("fit_display")) if fit_row is not None else "—"
            col3.markdown(
                f'<div class="overview-action-meta">FIT · {escape(fit_display)}</div>'
                f'<div class="overview-action-title">{escape(STATUS_LABELS.get(clean_value(row.get("current_status")), clean_value(row.get("current_status")) or "—"))}</div>',
                unsafe_allow_html=True,
            )
            action_extend, action_clear = actions.columns(2)
            if action_extend.button("+7d", key=f"overview_extend_{application_id}"):
                with st.spinner("Rescheduling follow-up…"):
                    extend_application_follow_up(application_id, days=7)
                st.rerun()
            if action_clear.button("Clear", key=f"overview_clear_{application_id}"):
                with st.spinner("Clearing follow-up…"):
                    clear_application_follow_up(application_id)
                st.rerun()


def render_progress_charts(status_df, domains_df, trend_df):
    left, right = st.columns(2)
    with left:
        st.subheader("Application pipeline")
        if status_df.empty:
            st.info("Your application pipeline will appear here after the first saved application.")
        else:
            chart = alt.Chart(status_df).mark_bar(cornerRadiusEnd=5).encode(
                x=alt.X("count:Q", title="Applications"),
                y=alt.Y("status:N", title=None, sort="-x"),
                color=alt.Color("status:N", legend=None),
                tooltip=[alt.Tooltip("status:N", title="Status"), alt.Tooltip("count:Q", title="Applications")],
            ).properties(height=250)
            st.altair_chart(chart, width="stretch")
    with right:
        st.subheader("Application activity")
        if trend_df.empty:
            st.info("Application activity will appear here as you build your history.")
        else:
            chart = alt.Chart(trend_df).mark_line(point=True, strokeWidth=3).encode(
                x=alt.X("month:N", title=None),
                y=alt.Y("count:Q", title="Applications"),
                tooltip=[alt.Tooltip("month:N", title="Month"), alt.Tooltip("count:Q", title="Applications")],
            ).properties(height=250)
            st.altair_chart(chart, width="stretch")


def render_market_signal(skill_areas_df, domains_df):
    left, right = st.columns(2)
    with left:
        st.subheader("Demand across your saved jobs")
        if skill_areas_df.empty:
            st.info("Skill demand will appear after job descriptions are analyzed.")
        else:
            chart = alt.Chart(skill_areas_df).mark_bar(cornerRadiusEnd=5).encode(
                y=alt.Y("skill_area:N", sort="-x", title=None),
                x=alt.X("job_count:Q", title="Jobs"),
                tooltip=[alt.Tooltip("skill_area:N", title="Area"), alt.Tooltip("job_count:Q", title="Jobs")],
            ).properties(height=280)
            st.altair_chart(chart, width="stretch")
    with right:
        st.subheader("Applications by domain")
        if domains_df.empty:
            st.info("Application domains will appear here after you save applications.")
        else:
            chart = alt.Chart(domains_df).mark_bar(cornerRadiusEnd=5).encode(
                y=alt.Y("domain:N", sort="-x", title=None),
                x=alt.X("count:Q", title="Applications"),
                tooltip=[alt.Tooltip("domain:N", title="Domain"), alt.Tooltip("count:Q", title="Applications")],
            ).properties(height=280)
            st.altair_chart(chart, width="stretch")


def render_recent_jobs(jobs_df):
    st.subheader("Recently analyzed jobs")
    if jobs_df.empty:
        st.info("Analyze your first job posting to start building your career intelligence library.")
        return

    display = jobs_df.head(5).copy()
    display["Company"] = display["company"].fillna("").replace("", "Unknown company")
    display["Role"] = display["job_title"].fillna("").replace("", "Untitled role")
    display["Domain"] = display["domain"].fillna("").replace("", "Unclassified")
    display["Fit"] = display.get("fit_display", pd.Series(index=display.index)).fillna("—")
    display["Analyzed"] = display["created_at"].astype(str).str[:10]
    table_df = pd.DataFrame(
        {
            "job_id": display["id"].astype(int),
            "Company": display["Company"],
            "Role": display["Role"],
            "Domain": display["Domain"],
            "Fit": display["Fit"],
            "Analyzed": display["Analyzed"],
        }
    )
    grid_builder = GridOptionsBuilder.from_dataframe(table_df)
    grid_builder.configure_default_column(sortable=True, resizable=True, filter=False)
    grid_builder.configure_selection(selection_mode="single", use_checkbox=False, suppressRowClickSelection=False)
    grid_builder.configure_grid_options(rowHeight=54, headerHeight=44, suppressCellFocus=True)
    grid_builder.configure_column("job_id", hide=True)
    grid_builder.configure_column("Company", flex=2, minWidth=170)
    grid_builder.configure_column("Role", flex=3, minWidth=250)
    grid_builder.configure_column("Domain", flex=2, minWidth=170)
    grid_builder.configure_column("Fit", flex=1.5, minWidth=155)
    grid_builder.configure_column("Analyzed", flex=1, minWidth=115)
    grid_response = AgGrid(
        table_df,
        gridOptions=grid_builder.build(),
        height=44 + len(table_df) * 54 + 4,
        theme="streamlit",
        update_on=["selectionChanged"],
        key=f"overview_recent_jobs_{st.session_state.get('overview_recent_jobs_reset', 0)}",
        show_toolbar=False,
        show_search=False,
        show_download_button=False,
        custom_css={
            ".ag-root-wrapper": {"border": "none", "border-radius": "0"},
            ".ag-header": {"background-color": "transparent", "border-bottom": "1px solid #303746"},
            ".ag-header-cell": {"color": "#b9c6d8", "font-size": "0.86rem", "font-weight": "600"},
            ".ag-row": {"background-color": "#0f1218 !important", "border-bottom": "1px solid #2a303b !important", "color": "#edf2f8", "cursor": "pointer"},
            ".ag-row-odd": {"background-color": "#151a23 !important"},
            ".ag-row-hover": {"background-color": "rgba(142, 197, 240, 0.08) !important"},
            ".ag-cell": {"align-items": "center", "display": "flex", "font-size": "0.88rem", "border-right": "none"},
        },
    )
    selected_rows = grid_response.selected_rows
    if selected_rows is not None and not selected_rows.empty:
        open_job_workspace(selected_rows.iloc[0]["job_id"])


def render_dashboard():
    applications_df = get_applications_df()
    jobs_df = get_jobs_df()
    followups_df = get_dashboard_followups_df()
    profiles_df = get_resume_profiles_df()
    skill_rows_df = get_skill_demand_rows_df()
    jobs_df = attach_fit_scores(jobs_df, skill_rows_df, profiles_df)
    fit_summary = build_job_fit_summary(jobs_df, skill_rows_df, profiles_df)
    render_header(jobs_df, applications_df, fit_summary)
    render_quick_actions()
    render_next_actions(followups_df, fit_summary)
    st.divider()
    render_progress_charts(get_status_summary_df(), get_domains_df(), get_application_trend_df())
    st.divider()
    render_market_signal(get_top_skill_areas_df(limit=6), get_domains_df())
    st.divider()
    render_recent_jobs(jobs_df)
