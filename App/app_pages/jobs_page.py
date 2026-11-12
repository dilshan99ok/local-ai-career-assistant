import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from App.app_utils.database import (
    get_applications_df,
    get_jobs_df,
    get_resume_profiles_df,
    get_skill_demand_rows_df,
)
from Scripts.job_fit import attach_fit_scores
from App.app_utils.navigation import navigate_to


def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def render_metric_cards(jobs_df):
    total_jobs = len(jobs_df)
    total_domains = jobs_df["domain"].nunique() if not jobs_df.empty else 0
    fit_scores = pd.to_numeric(jobs_df.get("fit_score", pd.Series(dtype=float)), errors="coerce")
    strong_matches = int((fit_scores >= 80).sum()) if not jobs_df.empty else 0
    latest_created_at = "—"

    if not jobs_df.empty and "created_at" in jobs_df.columns:
        latest_created_at = clean_value(jobs_df["created_at"].max()) or "—"
        if len(latest_created_at) > 16:
            latest_created_at = latest_created_at[:16]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Analyzed jobs", total_jobs)
    col2.metric("80%+ matches", strong_matches, help="Jobs where at least 80% of extracted skills appear in the matching category CV, or the default CV when no category matches.")
    col3.metric("Job domains", total_domains)
    col4.metric("Latest analysis", latest_created_at)


def render_filters(jobs_df):
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1.6, 1])

    with filter_col1:
        domains = ["All"]
        if not jobs_df.empty:
            domains += sorted(
                domain
                for domain in jobs_df["domain"].dropna().unique().tolist()
                if clean_value(domain)
            )
        selected_domain = st.selectbox(
            "Domain",
            domains,
            key="jobs_domain_filter",
        )

    with filter_col2:
        search_text = st.text_input(
            "Search jobs",
            key="jobs_search_filter",
            placeholder="Search company, job title, or domain",
        )

    with filter_col3:
        statuses = ["All"]
        if "application_status" in jobs_df.columns and not jobs_df.empty:
            statuses += sorted(
                status for status in jobs_df["application_status"].dropna().unique().tolist()
                if clean_value(status)
            )
        selected_status = st.selectbox("Application status", statuses, key="jobs_status_filter")

    return selected_domain, search_text, selected_status


def apply_filters(jobs_df, selected_domain, search_text, selected_status):
    filtered_df = jobs_df.copy()

    if selected_domain != "All":
        filtered_df = filtered_df[filtered_df["domain"] == selected_domain]

    if selected_status != "All" and "application_status" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["application_status"] == selected_status]

    search_text = clean_value(search_text).lower()
    if search_text:
        searchable_text = (
            filtered_df["company"].fillna("").astype(str)
            + " "
            + filtered_df["job_title"].fillna("").astype(str)
            + " "
            + filtered_df["domain"].fillna("").astype(str)
            + " "
            + filtered_df["location"].fillna("").astype(str)
            + " "
            + filtered_df.get("application_status", pd.Series(index=filtered_df.index)).fillna("").astype(str)
        ).str.lower()
        filtered_df = filtered_df[searchable_text.str.contains(search_text, regex=False)]

    return filtered_df


def open_job(job_id):
    navigate_to("Jobs", job_id=int(job_id))


def render_jobs_table(jobs_df):
    if jobs_df.empty:
        st.info("No analyzed jobs match the current filters.")
        return

    rows_per_page = 10
    total_rows = len(jobs_df)
    total_pages = max((total_rows - 1) // rows_per_page + 1, 1)
    current_page = st.session_state.get("jobs_current_page", 1)
    current_page = min(max(current_page, 1), total_pages)
    st.session_state["jobs_current_page"] = current_page

    start_index = (current_page - 1) * rows_per_page
    end_index = start_index + rows_per_page
    paginated_df = jobs_df.iloc[start_index:end_index]

    table_df = pd.DataFrame(
        {
            "job_id": [int(value) for value in paginated_df["id"]],
            "Company": [
                clean_value(value) or "Unknown company"
                for value in paginated_df["company"]
            ],
            "Job title": [
                clean_value(value) or "Untitled role"
                for value in paginated_df["job_title"]
            ],
            "Domain": [
                clean_value(value) or "Unclassified"
                for value in paginated_df["domain"]
            ],
            "Fit": [
                clean_value(value) or "—"
                for value in paginated_df.get("fit_display", pd.Series(index=paginated_df.index))
            ],
            "Status": [
                clean_value(value) or "Not applied"
                for value in paginated_df.get("application_status", pd.Series(index=paginated_df.index))
            ],
            "Analyzed": [
                (clean_value(value) or "—")[:10]
                for value in paginated_df["created_at"]
            ],
        },
    )

    st.caption("Click any row to open the complete job details. Click a column header to sort.")
    grid_builder = GridOptionsBuilder.from_dataframe(table_df)
    grid_builder.configure_default_column(
        sortable=True,
        resizable=True,
        filter=False,
        wrapText=False,
    )
    grid_builder.configure_grid_options(
        rowHeight=70,
        headerHeight=58,
        animateRows=False,
        suppressCellFocus=True,
    )
    grid_builder.configure_selection(
        selection_mode="single",
        use_checkbox=False,
        suppressRowClickSelection=False,
    )
    grid_builder.configure_column("job_id", hide=True)
    grid_builder.configure_column("Company", flex=2, minWidth=210)
    grid_builder.configure_column("Job title", flex=3, minWidth=300)
    grid_builder.configure_column("Domain", flex=2, minWidth=190)
    grid_builder.configure_column("Fit", flex=1.5, minWidth=165)
    grid_builder.configure_column("Status", flex=1.5, minWidth=150)
    grid_builder.configure_column("Analyzed", flex=1, minWidth=140)

    grid_height = max(180, min(850, 58 + len(table_df) * 70 + 4))

    grid_response = AgGrid(
        table_df,
        gridOptions=grid_builder.build(),
        height=grid_height,
        theme="streamlit",
        update_on=["selectionChanged", "sortChanged"],
        key=f"jobs_table_{st.session_state.get('jobs_table_reset', 0)}",
        show_toolbar=False,
        show_search=False,
        show_download_button=False,
        custom_css={
            ".ag-root-wrapper": {
                "border": "none",
                "border-radius": "0",
                "overflow": "hidden",
            },
            ".ag-header": {
                "background-color": "transparent",
                "border-bottom": "1px solid #303746",
            },
            ".ag-header-cell": {
                "color": "#b9c6d8",
                "font-size": "0.9rem",
                "font-weight": "600",
                "letter-spacing": "0.01em",
                "padding-left": "0",
                "padding-right": "22px",
            },
            ".ag-header-cell:hover": {
                "background-color": "rgba(255, 255, 255, 0.03)",
            },
            ".ag-row": {
                "background-color": "#0f1218 !important",
                "border-bottom": "1px solid #2a303b !important",
                "color": "#edf2f8",
                "cursor": "pointer",
            },
            ".ag-row-odd": {
                "background-color": "#151a23 !important",
            },
            ".ag-row-hover": {
                "background-color": "rgba(142, 197, 240, 0.08) !important",
            },
            ".ag-row-selected": {
                "background-color": "rgba(142, 197, 240, 0.14) !important",
                "border-bottom": "1px solid #4c8fc5 !important",
            },
            ".ag-cell": {
                "align-items": "center",
                "display": "flex",
                "font-size": "0.94rem",
                "padding-left": "0",
                "padding-right": "22px",
                "border-right": "none",
            },
            ".ag-icon": {
                "color": "#8ec5f0",
            },
        },
    )
    selected_rows = grid_response.selected_rows
    if selected_rows is not None and not selected_rows.empty:
        open_job(selected_rows.iloc[0]["job_id"])

    page_info, previous_col, page_col, next_col = st.columns([5, 1, 1.3, 1])
    page_info.caption(
        f"Showing jobs {start_index + 1}–{min(end_index, total_rows)} of {total_rows}"
    )
    if previous_col.button(
        "Previous",
        disabled=current_page <= 1,
        key="jobs_previous_page",
        width="stretch",
    ):
        st.session_state["jobs_current_page"] = current_page - 1
        st.rerun()
    page_col.markdown(
        f"<div style='text-align:center;padding-top:0.45rem;font-weight:600;'>Page {current_page} of {total_pages}</div>",
        unsafe_allow_html=True,
    )
    if next_col.button(
        "Next",
        disabled=current_page >= total_pages,
        key="jobs_next_page",
        width="stretch",
    ):
        st.session_state["jobs_current_page"] = current_page + 1
        st.rerun()


def render_jobs():
    st.header("Jobs")

    jobs_df = get_jobs_df()
    applications_df = get_applications_df()
    jobs_df = attach_fit_scores(
        jobs_df,
        get_skill_demand_rows_df(),
        get_resume_profiles_df(),
    )
    if not jobs_df.empty:
        status_by_source = {}
        if not applications_df.empty:
            status_by_source = (
                applications_df.sort_values(["id"], ascending=False)
                .drop_duplicates("source_file")
                .set_index("source_file")["current_status"]
                .to_dict()
            )
        jobs_df["application_status"] = jobs_df["source_file"].map(status_by_source).fillna("Not applied")

    action_col, _ = st.columns([1.4, 4])
    if action_col.button("＋ Add application", key="jobs_analyze_job", width="stretch"):
        st.session_state["open_add_application"] = True
        navigate_to("Applications")

    render_metric_cards(jobs_df)
    st.divider()

    selected_domain, search_text, selected_status = render_filters(jobs_df)
    filtered_jobs_df = apply_filters(jobs_df, selected_domain, search_text, selected_status)
    filter_signature = f"{selected_domain}|{search_text}|{selected_status}"
    if st.session_state.get("jobs_filter_signature") != filter_signature:
        st.session_state["jobs_current_page"] = 1
        st.session_state["jobs_filter_signature"] = filter_signature

    export_col, summary_col = st.columns([1, 4])
    if not filtered_jobs_df.empty:
        export_col.download_button(
            "Download CSV",
            data=filtered_jobs_df.to_csv(index=False).encode("utf-8"),
            file_name="ai_career_jobs.csv",
            mime="text/csv",
            key="download_jobs_csv",
        )
    summary_col.caption(
        f"Showing {len(filtered_jobs_df)} of {len(jobs_df)} jobs"
    )

    render_jobs_table(filtered_jobs_df)
