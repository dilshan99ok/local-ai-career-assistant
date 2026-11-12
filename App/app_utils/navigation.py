"""Session navigation for linked workspaces inside the single Streamlit page."""

import streamlit as st


PAGE_OPTIONS = (
    "Overview", "Applications", "Skills", "Jobs", "Resume & Gaps", "Tailoring Studio"
)


def current_route(state):
    page = state.get("current_page", state.get("selected_page", "Overview"))
    if page not in PAGE_OPTIONS:
        page = "Overview"
    job_id = state.get("selected_job_id") if page == "Jobs" and state.get("active_job_detail") else None
    return {"page": page, "job_id": int(job_id) if job_id else None}


def route_label(route):
    return "Job workspace" if route.get("page") == "Jobs" and route.get("job_id") else route["page"]


def push_route(state, page, job_id=None):
    if page not in PAGE_OPTIONS:
        raise ValueError(f"Unknown page: {page}")
    destination = {"page": page, "job_id": int(job_id) if page == "Jobs" and job_id is not None else None}
    if destination == current_route(state):
        return False
    history = list(state.get("navigation_history", []))
    history.append(current_route(state))
    state["navigation_history"] = history[-20:]
    state["requested_route"] = destination
    return True


def pop_route(state, fallback="Jobs"):
    history = list(state.get("navigation_history", []))
    destination = history.pop() if history else {"page": fallback, "job_id": None}
    state["navigation_history"] = history
    state["requested_route"] = destination
    return destination


def apply_requested_route(state):
    destination = state.pop("requested_route", None)
    if not destination:
        return
    state["scroll_to_top"] = state.get("scroll_to_top", 0) + 1
    state["current_page"] = destination["page"]
    state["active_job_detail"] = destination["page"] == "Jobs" and destination.get("job_id") is not None
    if state["active_job_detail"]:
        state["selected_job_id"] = int(destination["job_id"])
    elif destination["page"] == "Jobs":
        # AgGrid keeps row selection while a detail view is open. Remounting
        # clears only that selection; the search, filters, and page stay put.
        state["jobs_table_reset"] = state.get("jobs_table_reset", 0) + 1
    elif destination["page"] == "Overview":
        # Clear AgGrid's previous selection before reopening Overview.
        state["overview_recent_jobs_reset"] = state.get("overview_recent_jobs_reset", 0) + 1


def clear_sidebar_history(state):
    state["navigation_history"] = []
    state["active_job_detail"] = False
    state.pop("requested_route", None)
    if state.get("current_page", state.get("selected_page")) == "Jobs":
        state["jobs_table_reset"] = state.get("jobs_table_reset", 0) + 1
    if state.get("current_page", state.get("selected_page")) == "Overview":
        state["overview_recent_jobs_reset"] = state.get("overview_recent_jobs_reset", 0) + 1


def sidebar_navigate(state, page):
    """Open a main page, including its list when the page is already selected."""
    if page not in PAGE_OPTIONS:
        raise ValueError(f"Unknown page: {page}")
    if current_route(state) == {"page": page, "job_id": None}:
        return False
    clear_sidebar_history(state)
    state["current_page"] = page
    if page == "Overview":
        state["overview_recent_jobs_reset"] = state.get("overview_recent_jobs_reset", 0) + 1
    state["scroll_to_top"] = state.get("scroll_to_top", 0) + 1
    state.pop("editing_application_id", None)
    return True


def navigate_to(page, job_id=None):
    if push_route(st.session_state, page, job_id):
        if page == "Tailoring Studio" and job_id is not None:
            st.session_state["tailoring_job_id"] = int(job_id)
            st.session_state.pop("tailoring_job_selector", None)
        st.rerun()


def go_back(fallback="Jobs"):
    pop_route(st.session_state, fallback=fallback)
    st.rerun()


def render_back_navigation():
    history = st.session_state.get("navigation_history", [])
    if not history:
        return
    previous = history[-1]
    label = route_label(previous)
    button_col, trail_col = st.columns([1.4, 5])
    if button_col.button(f"← Back to {label}", key="workspace_back", width="stretch"):
        go_back()
    trail = [*history, current_route(st.session_state)]
    if len(trail) > 3:
        trail = trail[-3:]
        trail_col.caption("…  /  " + "  /  ".join(route_label(route) for route in trail))
    else:
        trail_col.caption("  /  ".join(route_label(route) for route in trail))


def render_scroll_reset():
    """Start each route at its heading, even when Streamlit retains scroll position."""
    state = st.session_state
    revision = state.get("scroll_to_top", 0)
    if not revision or revision == state.get("scroll_to_top_rendered"):
        return
    state["scroll_to_top_rendered"] = revision
    st.iframe(
        f"""
        <script>
          // Each route change gives this iframe a new revision so the script reruns.
          const revision = {revision};
          const reset = () => {{
            try {{
              const doc = window.parent.document;
              for (const el of [
                doc.querySelector('[data-testid="stAppViewContainer"]'),
                doc.querySelector('[data-testid="stMain"]'),
                doc.querySelector('section.main'),
                doc.scrollingElement,
              ]) {{
                if (el) el.scrollTop = 0;
              }}
              window.parent.scrollTo(0, 0);
            }} catch (e) {{ /* The sidebar and back buttons remain available. */ }}
          }};
          reset();
          requestAnimationFrame(reset);
          setTimeout(reset, 150);
        </script>
        """,
        height=1,
    )
