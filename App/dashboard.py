from html import escape

import streamlit as st

from App.app_utils.styles import apply_styles
from App.app_utils.navigation import (
    PAGE_OPTIONS, apply_requested_route, navigate_to,
    render_back_navigation, render_scroll_reset, sidebar_navigate,
)
from App.app_pages.dashboard_page import render_dashboard
from App.app_pages.applications_page import render_applications
from App.app_pages.skills_page import render_skills
from App.app_pages.jobs_page import render_jobs
from App.app_pages.job_detail_page import render_job_detail
from App.app_pages.resume_page import render_resume
from App.app_pages.tailoring_page import render_tailoring
from Scripts.chatgpt_auth import ChatGPTAuth, ChatGPTAuthError


st.set_page_config(
    page_title="AI Career Assistant",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_styles()

st.sidebar.markdown(
    """
    <div class="sidebar-brand">
        <div class="sidebar-title">AI Career Assistant</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.sidebar.button(
    "＋ Add application",
    key="sidebar_add_application",
    type="primary",
    use_container_width=True,
):
    st.session_state["open_add_application"] = True
    st.session_state.pop("editing_application_id", None)
    navigate_to("Applications")

page_options = list(PAGE_OPTIONS)
if "current_page" not in st.session_state:
    st.session_state["current_page"] = st.session_state.get("selected_page", "Overview")
if st.session_state.get("current_page") == "Job Detail":
    st.session_state["current_page"] = "Jobs"
    st.session_state["active_job_detail"] = bool(
        st.session_state.get("selected_job_id")
    )
if st.session_state.get("current_page") == "Dashboard":
    st.session_state["current_page"] = "Overview"
if st.session_state.get("current_page") not in page_options:
    st.session_state["current_page"] = "Overview"
requested_page = st.session_state.pop("requested_page", None)
if requested_page == "Dashboard":
    requested_page = "Overview"
if requested_page in page_options:
    st.session_state["requested_route"] = {"page": requested_page, "job_id": None}
apply_requested_route(st.session_state)

page = st.session_state["current_page"]
active_nav_key = page.lower().replace(" ", "_").replace("&", "and")
st.markdown(
    f"""<style>
    section[data-testid="stSidebar"] .st-key-sidebar_page_{active_nav_key} button {{
        background: rgba(142,197,240,0.14) !important;
        border-color: rgba(142,197,240,0.24) !important;
        color: #fff !important;
    }}
    </style>""",
    unsafe_allow_html=True,
)
for option in page_options:
    nav_key = option.lower().replace(" ", "_").replace("&", "and")
    if st.sidebar.button(option, key=f"sidebar_page_{nav_key}"):
        if sidebar_navigate(st.session_state, option):
            st.rerun()

with st.sidebar.container():
    # Keep the account controls in one sidebar block so the entire footer can
    # be pushed down together without positioning individual Streamlit widgets.
    st.markdown('<div class="sidebar-footer-anchor"></div>', unsafe_allow_html=True)

    auth = ChatGPTAuth()
    try:
        auth_status = auth.get_status()
    except ChatGPTAuthError:
        auth_status = {"signed_in": False, "email": "", "plan_usage_authorized": False}
        st.error("Saved ChatGPT sign-in is invalid")
    if auth_status["signed_in"]:
        signed_in_label = auth_status["email"] or "ChatGPT account"
        account_state = "" if auth_status["plan_usage_authorized"] else '<div class="sidebar-account-state">AI access unavailable</div>'
        account_class = "connected" if auth_status["plan_usage_authorized"] else "attention"
        st.markdown(
            f"""
            <div class="sidebar-account {account_class}">
                <div class="sidebar-account-email">{escape(signed_in_label)}</div>
                {account_state}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Sign out", key="sign_out_chatgpt"):
            auth.sign_out()
            st.rerun()
    else:
        st.markdown(
            """
            <div class="sidebar-account attention">
                <div class="sidebar-account-email">Sign in to use AI</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code("python Scripts/sign_in_with_chatgpt.py", language="powershell")

render_scroll_reset()
render_back_navigation()

if st.session_state.get("active_job_detail") and page == "Jobs":
    render_job_detail()
elif st.session_state.get("active_job_detail"):
    st.session_state["active_job_detail"] = False
    st.session_state["jobs_table_reset"] = st.session_state.get("jobs_table_reset", 0) + 1
    page = st.session_state["current_page"]

if not st.session_state.get("active_job_detail") and page == "Overview":
    render_dashboard()

elif not st.session_state.get("active_job_detail") and page == "Applications":
    render_applications()

elif not st.session_state.get("active_job_detail") and page == "Skills":
    render_skills()

elif not st.session_state.get("active_job_detail") and page == "Jobs":
    render_jobs()

elif not st.session_state.get("active_job_detail") and page == "Resume & Gaps":
    render_resume()

elif not st.session_state.get("active_job_detail") and page == "Tailoring Studio":
    render_tailoring()
