import json
import base64
from html import escape
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from App.app_utils.database import (
    delete_resume_profile,
    attach_resume_source_file,
    get_resume_profiles_df,
    get_resume_source_file,
    get_specific_skills_df,
    save_resume_profile,
)
from Scripts.resume_helper import extract_resume_skills
from Scripts.resume_profiles import PROFILE_CATEGORIES, category_from_filename
from Scripts.resume_import import (
    ResumeImportError,
    extract_resume_details,
    extract_resume_text,
)
from Scripts.resume_preview import ResumePreviewError, docx_to_pdf


def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.lower() in {"none", "nan"} else value


def load_skills(profile_row):
    try:
        skills = json.loads(profile_row.get("skills_json", "[]"))
    except (TypeError, json.JSONDecodeError):
        skills = []
    return [item for item in skills if isinstance(item, dict)]


@st.cache_data(show_spinner=False, max_entries=8)
def cached_docx_to_pdf(data):
    return docx_to_pdf(data)


@st.cache_data(show_spinner=False, max_entries=16)
def cached_resume_text(filename, data):
    return extract_resume_text(filename, data)


def display_pdf(data):
    encoded = base64.b64encode(data).decode("ascii")
    st.iframe(f"data:application/pdf;base64,{encoded}", height=680)


@st.dialog("CV preview", width="large")
def show_resume_preview(profile_id, profile_name, resume_text):
    st.caption(profile_name)
    filename, source_file = get_resume_source_file(profile_id)
    if not source_file and Path(filename).suffix.lower() in {".pdf", ".docx"}:
        st.info("The original file was not stored when this CV was added. Attach it to see the formatted preview.")
        uploaded = st.file_uploader(
            "Attach original CV", type=[Path(filename).suffix.lower().lstrip(".")],
            key=f"attach_cv_source_{profile_id}",
            max_upload_size=25,
        )
        if uploaded and st.button("Attach file", key=f"attach_cv_source_button_{profile_id}"):
            candidate = uploaded.getvalue()
            try:
                with st.spinner("Checking original CV…"):
                    if not cached_resume_text(uploaded.name, candidate):
                        raise ResumeImportError("No readable text found in this file.")
            except ResumeImportError as error:
                st.error(str(error))
            else:
                source_file = candidate
                with st.spinner("Attaching original CV…"):
                    attach_resume_source_file(profile_id, uploaded.name, source_file)
                filename = uploaded.name

    if source_file:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            display_pdf(source_file)
            st.download_button("Download original", source_file, file_name=filename)
            return
        if suffix == ".docx":
            try:
                with st.spinner("Opening CV preview…"):
                    display_pdf(cached_docx_to_pdf(source_file))
                st.download_button("Download original", source_file, file_name=filename)
                return
            except ResumePreviewError:
                st.warning("Word could not display this DOCX. Download the original to view its layout.")
        st.download_button("Download original CV", source_file, file_name=filename)

    st.markdown(
        f'<div class="resume-preview-sheet">{escape(resume_text)}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Text preview")


def render_add_cvs(profiles_df):
    st.subheader("Add a CV")
    mode = st.segmented_control(
        "Source", ["Upload files", "Paste text"], default="Upload files",
        key="resume_add_mode", label_visibility="collapsed",
    )
    existing_names = (
        {clean_value(name).casefold() for name in profiles_df["profile_name"]}
        if not profiles_df.empty else set()
    )

    if mode == "Upload files":
        generation = st.session_state.get("resume_batch_generation", 0)
        files = st.file_uploader(
            "Drop CVs here or browse",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key=f"resume_batch_files_{generation}",
            help="DOCX works best for later editing. PDF and TXT are also accepted.",
            max_upload_size=25,
        )
        if not files:
            return

        prepared = []
        errors = []
        with st.form(f"resume_batch_form_{generation}", enter_to_submit=False):
            for index, uploaded in enumerate(files):
                if index:
                    st.divider()
                with st.container(key=f"resume_upload_file_{generation}_{index}"):
                    st.markdown(f"**{escape(uploaded.name)}**")
                    try:
                        with st.spinner(f"Reading {uploaded.name}…"):
                            extracted = cached_resume_text(uploaded.name, uploaded.getvalue())
                        if not extracted:
                            raise ResumeImportError("No readable text found.")
                    except ResumeImportError as error:
                        errors.append(f"{uploaded.name}: {error}")
                        st.error(str(error))
                        continue

                    name_col, category_col = st.columns([1.3, 1], gap="medium")
                    name = name_col.text_input(
                        "CV name",
                        value=Path(uploaded.name).stem.replace("_", " ").replace("-", " ").title(),
                        key=f"batch_resume_name_{generation}_{index}",
                    )
                    suggested = category_from_filename(uploaded.name)
                    category = category_col.selectbox(
                        "Job category", PROFILE_CATEGORIES,
                        index=PROFILE_CATEGORIES.index(suggested),
                        key=f"batch_resume_category_{generation}_{index}",
                    )
                    with st.expander("Review extracted text"):
                        reviewed_text = st.text_area(
                            "CV text", value=extracted, height=220,
                            key=f"batch_resume_preview_{generation}_{index}",
                            label_visibility="collapsed",
                        )
                    prepared.append((name.strip(), category, uploaded.name, reviewed_text.strip(), uploaded.getvalue()))
            submitted = st.form_submit_button(
                "Save CV" if len(files) == 1 else f"Save {len(files)} CVs", type="primary"
            )

        if submitted:
            if errors or len(prepared) != len(files):
                st.error("Remove unreadable files before saving.")
                return
            names = [row[0].casefold() for row in prepared]
            if not all(names) or len(set(names)) != len(names) or any(name in existing_names for name in names):
                st.error("Each CV needs a unique name.")
                return
            if any(not row[3] for row in prepared):
                st.error("Each CV needs readable text.")
                return
            with st.spinner("Saving CVs…", show_time=True):
                progress = st.progress(0, text="Saving CVs") if len(prepared) > 1 else None
                for index, (name, category, filename, resume_text, source_file) in enumerate(prepared, 1):
                    save_resume_profile(
                        name, resume_text, extract_resume_skills(resume_text),
                        source_filename=filename,
                        source_type=Path(filename).suffix.upper().lstrip(".") or "File",
                        source_file=source_file,
                        details=extract_resume_details(resume_text),
                        target_domain=category,
                    )
                    if progress:
                        progress.progress(index / len(prepared), text=f"Saved {index} of {len(prepared)} CVs")
                if progress:
                    progress.empty()
            st.session_state["resume_batch_saved"] = len(prepared)
            st.session_state["resume_batch_generation"] = generation + 1
            st.rerun()
        return

    generation = st.session_state.get("resume_single_generation", 0)
    with st.form(f"resume_profile_form_{generation}", enter_to_submit=False):
        name_col, category_col = st.columns([1.3, 1], gap="medium")
        profile_name = name_col.text_input("CV name", key=f"resume_profile_name_editor_{generation}")
        category = category_col.selectbox(
            "Job category", PROFILE_CATEGORIES, key=f"resume_profile_category_editor_{generation}"
        )
        resume_text = st.text_area(
            "CV text", height=280, placeholder="Paste your CV here.",
            key=f"resume_text_editor_{generation}",
        )
        submitted = st.form_submit_button("Save CV", type="primary")
        if submitted:
            if not profile_name.strip() or not resume_text.strip():
                st.error("Add a name and CV text.")
            elif profile_name.strip().casefold() in existing_names:
                st.error("A CV with this name already exists.")
            else:
                with st.spinner("Saving CV…"):
                    save_resume_profile(
                        profile_name.strip(), resume_text,
                        extract_resume_skills(resume_text),
                        source_type="Pasted text",
                        details=extract_resume_details(resume_text),
                        target_domain=category,
                    )
                st.session_state["resume_single_saved"] = True
                st.session_state["resume_single_generation"] = generation + 1
                st.rerun()


def render_profile_tab(profiles_df):
    if st.session_state.pop("resume_single_saved", False):
        st.success("CV saved.")
    if st.session_state.pop("resume_batch_saved", None):
        st.success("CVs saved.")
    if st.session_state.pop("resume_profile_removed", False):
        st.success("CV removed. Job drafts were kept.")

    with st.container(border=True, key="resume_upload_panel"):
        render_add_cvs(profiles_df)
    if profiles_df.empty:
        st.info("No CVs yet.")
        return None

    st.subheader("Your CVs")
    selected_id = st.session_state.get("resume_inspect_id")
    if selected_id not in set(profiles_df["id"].astype(int)):
        selected_id = int(profiles_df.iloc[0]["id"])
        st.session_state["resume_inspect_id"] = selected_id

    for _, row in profiles_df.iterrows():
        profile_id = int(row["id"])
        is_selected = profile_id == selected_id
        with st.container(border=True, key=f"resume_cv_{profile_id}"):
            info_col, actions_col = st.columns([4.6, 2.2], vertical_alignment="center")
            with info_col:
                label = escape(clean_value(row["profile_name"]))
                category = escape(clean_value(row.get("target_domain")) or "General")
                filename = escape(clean_value(row.get("source_filename")) or "Pasted text")
                category_badge = f'<span class="resume-card-category">{category}</span>'
                badge = '<span class="resume-card-selected">Inspecting</span>' if is_selected else ""
                st.markdown(
                    f'<div class="resume-card-name">{label}{category_badge}{badge}</div>'
                    f'<div class="resume-card-meta">{filename}</div>',
                    unsafe_allow_html=True,
                )
            with actions_col:
                view_col, inspect_col, remove_col = st.columns([1, 1.2, 1], gap="small")
                if view_col.button(
                    "View", key=f"view_resume_profile_{profile_id}",
                    type="tertiary", icon=":material/visibility:",
                ):
                    show_resume_preview(
                        profile_id,
                        clean_value(row["profile_name"]),
                        clean_value(row.get("resume_text")),
                    )
                if not is_selected and inspect_col.button(
                    "Inspect", key=f"inspect_resume_profile_{profile_id}",
                    type="tertiary", icon=":material/analytics:",
                ):
                    st.session_state["resume_inspect_id"] = profile_id
                    st.rerun()
                if remove_col.button(
                    "Remove", key=f"remove_resume_profile_{profile_id}",
                    type="tertiary", icon=":material/delete_outline:",
                ):
                    st.session_state["confirm_remove_cv_id"] = profile_id
                    st.rerun()
            if st.session_state.get("confirm_remove_cv_id") == profile_id:
                st.warning("Remove this CV? Saved job drafts will remain available.")
                confirm_col, cancel_col = st.columns([1, 1])
                if confirm_col.button("Remove CV", key=f"confirm_remove_resume_profile_{profile_id}",
                                      type="primary"):
                    with st.spinner("Removing CV…"):
                        delete_resume_profile(profile_id)
                    st.session_state.pop("confirm_remove_cv_id", None)
                    st.session_state["resume_profile_removed"] = True
                    st.rerun()
                if cancel_col.button("Cancel", key=f"cancel_remove_resume_profile_{profile_id}"):
                    st.session_state.pop("confirm_remove_cv_id", None)
                    st.rerun()

    selected_row = profiles_df[profiles_df["id"] == selected_id].iloc[0]
    return selected_row


def render_inventory_tab(selected_row):
    if selected_row is None:
        return
    st.subheader("Skills in this CV")
    rows = [
        {
            "Skill": clean_value(item.get("skill")),
            "Category": clean_value(item.get("basket")) or "Other",
        }
        for item in load_skills(selected_row)
        if clean_value(item.get("skill"))
    ]
    if not rows:
        st.info("No skills detected yet.")
        return

    inventory = pd.DataFrame(rows)
    inventory["key"] = inventory["Skill"].str.casefold()
    inventory = inventory.drop_duplicates(["Category", "key"])
    summary = (
        inventory.groupby("Category", as_index=False)
        .size().rename(columns={"size": "Skills"})
        .sort_values(["Skills", "Category"], ascending=[False, True])
    )
    chart_rows = summary.head(8).copy()
    if len(summary) > 8:
        chart_rows = pd.concat([
            chart_rows,
            pd.DataFrame([{"Category": "Other areas", "Skills": int(summary.iloc[8:]["Skills"].sum())}]),
        ], ignore_index=True)
    category = st.selectbox(
        "Explore area", summary["Category"].tolist(),
        key=f"resume_skill_area_{int(selected_row['id'])}",
    )
    bars = alt.Chart(chart_rows).mark_bar(
        color="#72b9f2", cornerRadiusEnd=5
    ).encode(
        y=alt.Y("Category:N", sort="-x", title=None, axis=alt.Axis(labelLimit=190)),
        x=alt.X("Skills:Q", title=None, axis=alt.Axis(tickMinStep=1),
                scale=alt.Scale(domain=[0, int(chart_rows["Skills"].max()) + 2])),
        tooltip=[alt.Tooltip("Category:N", title="Area"), alt.Tooltip("Skills:Q")],
    )
    chart = (bars + bars.mark_text(align="left", dx=6, color="#e3edf7").encode(
        text=alt.Text("Skills:Q")
    )).properties(height=32 * len(chart_rows) + 12).configure_axis(labelFontSize=12)
    st.altair_chart(chart, width="stretch")

    names = inventory[inventory["Category"] == category]["Skill"].sort_values(key=lambda values: values.str.casefold())
    st.markdown(
        '<div class="resume-skill-chips">'
        + "".join(f'<span class="resume-skill-chip">{escape(name)}</span>' for name in names)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_gaps_tab(selected_row):
    if selected_row is None:
        return
    st.subheader("Potential gaps")
    resume_skills = load_skills(selected_row)
    known = {clean_value(item.get("skill")).lower() for item in resume_skills}
    demand_df = get_specific_skills_df()
    if demand_df.empty:
        st.info("Analyze jobs to see demand.")
        return

    gaps = demand_df[~demand_df["Specific Skill"].str.lower().isin(known)].copy()
    gaps = gaps.rename(columns={"Skill Basket": "Category", "Specific Skill": "Skill", "Count": "Job mentions"})
    if gaps.empty:
        st.success("No gaps detected in saved jobs.")
        return

    gaps["Category"] = gaps["Category"].fillna("Other")
    gaps["Skill"] = gaps["Skill"].fillna("")
    gaps["Job mentions"] = pd.to_numeric(gaps["Job mentions"], errors="coerce").fillna(0).astype(int)
    categories = ["All areas"] + sorted(gaps["Category"].unique().tolist())
    category = st.selectbox(
        "Filter by area", categories,
        key=f"resume_gap_area_{int(selected_row['id'])}",
    )
    filtered = gaps if category == "All areas" else gaps[gaps["Category"] == category]
    top_gaps = filtered.sort_values(["Job mentions", "Skill"], ascending=[False, True]).head(9)
    bars = alt.Chart(top_gaps).mark_bar(
        color="#f1b86c", cornerRadiusEnd=5
    ).encode(
        y=alt.Y("Skill:N", sort="-x", title=None, axis=alt.Axis(labelLimit=190)),
        x=alt.X("Job mentions:Q", title=None, axis=alt.Axis(tickMinStep=1),
                scale=alt.Scale(domain=[0, int(top_gaps["Job mentions"].max()) + 2])),
        tooltip=[
            alt.Tooltip("Skill:N"), alt.Tooltip("Category:N", title="Area"),
            alt.Tooltip("Job mentions:Q"),
        ],
    )
    chart = (bars + bars.mark_text(align="left", dx=6, color="#e3edf7").encode(
        text=alt.Text("Job mentions:Q")
    )).properties(height=32 * len(top_gaps) + 12).configure_axis(labelFontSize=12)
    st.altair_chart(chart, width="stretch")
    if len(filtered) > len(top_gaps):
        with st.expander(f"All {len(filtered)} potential gaps"):
            st.caption("Review before adding a skill to your CV.")
            st.dataframe(
                filtered.sort_values("Job mentions", ascending=False),
                width="stretch", hide_index=True, height=350,
            )


def render_resume():
    st.title("Resumes")

    profiles_df = get_resume_profiles_df()
    selected_row = render_profile_tab(profiles_df)
    if selected_row is not None:
        st.divider()
        skills_col, gaps_col = st.columns(2, gap="large")
        with skills_col:
            render_inventory_tab(selected_row)
        with gaps_col:
            render_gaps_tab(selected_row)
