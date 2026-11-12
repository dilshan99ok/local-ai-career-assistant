"""One list of tracked applications, enriched by their analyzed job details."""

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder

from App.app_utils.navigation import navigate_to


COLUMNS = [
    "job_id", "application_id", "company", "job_title", "domain",
    "fit_display", "current_status", "date_applied", "follow_up_date",
    "source_file", "notes", "sort_at",
]


def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def tracked_jobs(jobs_df, applications_df):
    """Return analyzed jobs that belong to at least one saved application."""
    if jobs_df.empty or applications_df.empty:
        return jobs_df.iloc[0:0].copy()
    job_ids = set(pd.to_numeric(applications_df["job_id"], errors="coerce").dropna().astype(int))
    return jobs_df[jobs_df["id"].isin(job_ids)].copy()


def build_opportunities_df(jobs_df, applications_df):
    """Keep every application, including ones without an analyzed job."""
    jobs_by_id = {int(row["id"]): row for _, row in jobs_df.iterrows()}
    rows = []

    for _, application in applications_df.iterrows():
        source = clean_value(application.get("source_file"))
        linked_id = pd.to_numeric(application.get("job_id"), errors="coerce")
        job = jobs_by_id.get(int(linked_id)) if pd.notna(linked_id) else None
        rows.append({
            "job_id": int(job["id"]) if job is not None else None,
            "application_id": int(application["id"]),
            "company": clean_value(application.get("company")) or (clean_value(job.get("company")) if job is not None else ""),
            "job_title": clean_value(application.get("job_title")) or (clean_value(job.get("job_title")) if job is not None else ""),
            "domain": clean_value(application.get("domain")) or (clean_value(job.get("domain")) if job is not None else ""),
            "fit_display": clean_value(job.get("fit_display")) if job is not None else "",
            "current_status": clean_value(application.get("current_status")) or "Applied",
            "date_applied": clean_value(application.get("date_applied")),
            "follow_up_date": clean_value(application.get("follow_up_date")),
            "source_file": source,
            "notes": clean_value(application.get("notes")),
            "sort_at": clean_value(application.get("date_applied")) or clean_value(application.get("created_at")),
        })

    return pd.DataFrame(rows, columns=COLUMNS).sort_values("sort_at", ascending=False, kind="stable").reset_index(drop=True)


def filter_opportunities(df, search, domain, status):
    filtered = df.copy()
    if domain != "All":
        filtered = filtered[filtered["domain"] == domain]
    if status != "All":
        filtered = filtered[filtered["current_status"] == status]
    search = clean_value(search).casefold()
    if search:
        searchable = (
            filtered["company"].fillna("").astype(str) + " "
            + filtered["job_title"].fillna("").astype(str) + " "
            + filtered["domain"].fillna("").astype(str) + " "
            + filtered["notes"].fillna("").astype(str)
        ).str.casefold()
        filtered = filtered[searchable.str.contains(search, regex=False)]
    return filtered


def open_opportunity(row):
    job_id = row.get("job_id")
    application_id = row.get("application_id")
    if pd.notna(job_id):
        st.session_state["selected_application_id"] = int(application_id) if pd.notna(application_id) else None
        st.session_state.pop("editing_application_id", None)
        navigate_to("Applications", job_id=int(job_id))
    elif pd.notna(application_id):
        st.session_state["editing_application_id"] = int(application_id)
        st.session_state["scroll_to_top"] = st.session_state.get("scroll_to_top", 0) + 1
        st.rerun()


def render_opportunities_table(df):
    if df.empty:
        st.info("No applications match these filters.")
        return

    rows_per_page = 10
    total_rows = len(df)
    total_pages = max((total_rows - 1) // rows_per_page + 1, 1)
    page = min(max(int(st.session_state.get("opportunities_current_page", 1)), 1), total_pages)
    st.session_state["opportunities_current_page"] = page
    start = (page - 1) * rows_per_page
    visible = df.iloc[start:start + rows_per_page]
    table = pd.DataFrame({
        "row_key": [int(value) for value in visible["application_id"]],
        "Company": [clean_value(value) or "Unknown company" for value in visible["company"]],
        "Job title": [clean_value(value) or "Untitled role" for value in visible["job_title"]],
        "Domain": [clean_value(value) or "Unclassified" for value in visible["domain"]],
        "Fit": [clean_value(value) or "—" for value in visible["fit_display"]],
        "Status": visible["current_status"].tolist(),
        "Applied": [clean_value(value)[:10] or "—" for value in visible["date_applied"]],
        "Follow-up": [clean_value(value)[:10] or "—" for value in visible["follow_up_date"]],
    })

    grid = GridOptionsBuilder.from_dataframe(table)
    grid.configure_default_column(sortable=True, resizable=True, filter=False, wrapText=False)
    grid.configure_grid_options(rowHeight=64, headerHeight=52, animateRows=False, suppressCellFocus=True)
    grid.configure_selection(selection_mode="single", use_checkbox=False, suppressRowClickSelection=False)
    grid.configure_column("row_key", hide=True)
    grid.configure_column("Company", flex=2, minWidth=185)
    grid.configure_column("Job title", flex=3, minWidth=270)
    grid.configure_column("Domain", flex=1.5, minWidth=170)
    grid.configure_column("Fit", flex=1.2, minWidth=145)
    grid.configure_column("Status", flex=1.2, minWidth=140)
    grid.configure_column("Applied", flex=1.1, minWidth=135)
    grid.configure_column("Follow-up", flex=1.1, minWidth=135)

    response = AgGrid(
        table,
        gridOptions=grid.build(),
        height=max(180, min(760, 52 + len(table) * 64 + 4)),
        theme="streamlit",
        update_on=["selectionChanged", "sortChanged"],
        key=f"opportunities_table_{st.session_state.get('opportunities_table_reset', 0)}",
        show_toolbar=False,
        show_search=False,
        show_download_button=False,
        custom_css={
            ".ag-root-wrapper": {"border": "none", "border-radius": "0", "overflow": "hidden"},
            ".ag-header": {"background-color": "transparent", "border-bottom": "1px solid #303746"},
            ".ag-header-cell": {"color": "#b9c6d8", "font-size": "0.9rem", "font-weight": "600", "padding-left": "0", "padding-right": "18px"},
            ".ag-row": {"background-color": "#0f1218 !important", "border-bottom": "1px solid #2a303b !important", "color": "#edf2f8", "cursor": "pointer"},
            ".ag-row-odd": {"background-color": "#151a23 !important"},
            ".ag-row-hover": {"background-color": "rgba(142, 197, 240, 0.08) !important"},
            ".ag-row-selected": {"background-color": "rgba(142, 197, 240, 0.14) !important", "border-bottom": "1px solid #4c8fc5 !important"},
            ".ag-cell": {"align-items": "center", "display": "flex", "font-size": "0.94rem", "padding-left": "0", "padding-right": "18px", "border-right": "none"},
        },
    )
    if response.selected_rows is not None and not response.selected_rows.empty:
        key = response.selected_rows.iloc[0]["row_key"]
        selected = visible.iloc[table.index[table["row_key"] == key][0]]
        open_opportunity(selected)

    count_col, previous_col, page_col, next_col = st.columns([5, 1, 1.3, 1])
    count_col.caption(f"Showing {start + 1}–{min(start + rows_per_page, total_rows)} of {total_rows}")
    if previous_col.button("Previous", disabled=page <= 1, key="opportunities_previous_page", width="stretch"):
        st.session_state["opportunities_current_page"] = page - 1
        st.rerun()
    page_col.markdown(f"<div style='text-align:center;padding-top:0.45rem;font-weight:600;'>Page {page} of {total_pages}</div>", unsafe_allow_html=True)
    if next_col.button("Next", disabled=page >= total_pages, key="opportunities_next_page", width="stretch"):
        st.session_state["opportunities_current_page"] = page + 1
        st.rerun()
