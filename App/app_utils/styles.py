import streamlit as st


def apply_styles():
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2.5rem;
            max-width: 95%;
        }

        section[data-testid="stSidebar"] {
            width: 268px !important;
            background: #171820 !important;
            border-right: 1px solid rgba(255,255,255,0.07);
        }

        section[data-testid="stSidebar"] > div:first-child {
            width: 268px !important;
        }

        section[data-testid="stSidebar"] .block-container {
            min-height: 100vh;
            height: 100vh;
            box-sizing: border-box;
            padding: 1.25rem 1rem 1rem 1rem !important;
            display: flex;
            flex-direction: column;
        }

        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            min-height: 100vh;
            height: 100%;
            display: flex;
            flex-direction: column;
        }

        section[data-testid="stSidebar"] .block-container > [data-testid="stVerticalBlock"],
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"] {
            min-height: 100%;
            display: flex;
            flex-direction: column;
        }

        .sidebar-brand {
            padding: 0.25rem 0.35rem 0.85rem 0.35rem;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 0.75rem;
        }

        .sidebar-kicker,
        .sidebar-section-label,
        .sidebar-account-label {
            color: #8ec5f0;
            font-size: 0.62rem;
            font-weight: 750;
            letter-spacing: 0.14em;
        }

        .sidebar-title {
            color: #f4f7fb;
            font-size: 1.16rem;
            font-weight: 750;
            letter-spacing: -0.02em;
            margin-top: 0;
        }

        .sidebar-copy {
            color: rgba(232,238,246,0.56);
            font-size: 0.78rem;
            line-height: 1.45;
            margin-top: 0.45rem;
        }

        .sidebar-account {
            border: 1px solid rgba(255,255,255,0.09);
            border-radius: 0.65rem;
            padding: 0.75rem 0.8rem;
            margin: 0 0.1rem 0.55rem 0.1rem;
        }

        .sidebar-account.connected {
            background: rgba(47, 167, 107, 0.14);
            border-color: rgba(83, 204, 139, 0.25);
        }

        .sidebar-account.attention {
            background: rgba(226, 168, 64, 0.1);
            border-color: rgba(226, 168, 64, 0.25);
        }

        .sidebar-account-label {
            color: rgba(232,238,246,0.55);
            font-size: 0.58rem;
        }

        .sidebar-account-email {
            color: #f4f7fb;
            font-size: 0.82rem;
            font-weight: 650;
            line-height: 1.35;
            margin-top: 0;
            overflow-wrap: anywhere;
        }

        .sidebar-account-state {
            color: rgba(232,238,246,0.58);
            font-size: 0.7rem;
            margin-top: 0.25rem;
        }

        .sidebar-section-label {
            color: rgba(232,238,246,0.46);
            margin: 1.15rem 0 0.45rem 0.35rem;
        }

        .sidebar-footer-anchor {
            border-top: 1px solid rgba(255,255,255,0.08);
            height: 0.9rem;
        }

        section[data-testid="stSidebar"] [class*="st-key-sidebar_page_"] button {
            border: 1px solid transparent;
            border-radius: 0.58rem;
            color: rgba(244,247,251,0.76);
            cursor: pointer;
            min-height: 2.1rem;
            padding: 0.42rem 0.58rem !important;
            justify-content: flex-start;
            background: transparent;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }

        section[data-testid="stSidebar"] [class*="st-key-sidebar_page_"] button:hover {
            background: rgba(255,255,255,0.055);
            border-color: rgba(255,255,255,0.08);
            color: #ffffff;
        }

        section[data-testid="stSidebar"] [class*="st-key-sidebar_page_"] button p {
            font-size: 0.84rem !important;
            font-weight: 650 !important;
            margin: 0 !important;
        }

        section[data-testid="stSidebar"] button {
            border-radius: 0.5rem !important;
        }

        section[data-testid="stSidebar"] [data-testid="stButton"] button {
            width: 100%;
            min-height: 2.25rem;
        }

        section[data-testid="stSidebar"] [data-testid="stCodeBlock"] {
            margin-top: 0.65rem;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(255,255,255,0.09) !important;
            border-radius: 0.8rem !important;
            background: rgba(255,255,255,0.018);
        }

        .st-key-resume_upload_panel {
            max-width: 1100px;
        }

        .st-key-resume_upload_panel [data-testid="stFileUploader"] {
            padding: 0.65rem;
            border: 1px dashed rgba(142,197,240,0.5);
            border-radius: 0.75rem;
            background: rgba(142,197,240,0.035);
        }

        .st-key-resume_upload_panel [data-testid="stFileUploaderDropzone"] {
            min-height: 4.5rem;
            background: transparent;
        }

        .st-key-resume_upload_panel [class*="st-key-resume_upload_file_"] {
            padding: 0.45rem 0.2rem;
        }

        .st-key-resume_cv_list {
            max-width: 1100px;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(.resume-card-name) {
            max-width: 1100px;
            padding: 0.45rem 0.8rem !important;
        }

        .resume-list-divider {
            border-top: 1px solid rgba(255,255,255,0.09);
            margin: 0.25rem 0;
        }

        .resume-card-name {
            color: #f4f7fb;
            font-size: 0.92rem;
            font-weight: 700;
            line-height: 1.3;
        }

        .resume-card-meta {
            color: rgba(232,238,246,0.58);
            font-size: 0.76rem;
            margin-top: 0.15rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .resume-card-category {
            display: inline-block;
            margin-left: 0.6rem;
            padding: 0.1rem 0.42rem;
            border: 1px solid rgba(142,197,240,0.28);
            border-radius: 999px;
            color: #d4e9fa;
            background: rgba(142,197,240,0.08);
            font-size: 0.68rem;
            font-weight: 650;
            vertical-align: middle;
        }

        .resume-preview-sheet {
            max-height: 65vh;
            overflow-y: auto;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            padding: 1.5rem;
            border-radius: 0.5rem;
            background: #f9fafb;
            color: #17212d;
            font-size: 0.9rem;
            line-height: 1.55;
        }

        div[data-testid="stVerticalBlockBorderWrapper"]:has(.resume-card-name) div[data-testid="stButton"] button {
            min-height: 1.9rem;
            padding: 0.2rem 0.45rem;
            font-size: 0.8rem;
        }

        .resume-skill-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.42rem;
            margin-top: 0.35rem;
        }

        .resume-skill-chip {
            padding: 0.3rem 0.58rem;
            border: 1px solid rgba(142,197,240,0.25);
            border-radius: 999px;
            color: #d9eaf6;
            background: rgba(142,197,240,0.075);
            font-size: 0.78rem;
        }

        .job-cv-comparison,
        .job-skill-evidence {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
            gap: 0.8rem;
            margin: 0.5rem 0 1.4rem;
        }

        .job-cv-card,
        .job-skill-panel {
            min-width: 0;
            border: 1px solid rgba(255,255,255,0.11);
            border-radius: 0.75rem;
            background: rgba(255,255,255,0.025);
            padding: 0.95rem 1.1rem;
        }

        .job-cv-card.recommended {
            border-color: rgba(112,190,242,0.7);
            background: rgba(112,190,242,0.08);
        }

        .job-cv-top,
        .job-skill-heading {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.8rem;
        }

        .job-cv-name {
            color: #f4f7fb;
            font-size: 0.96rem;
            font-weight: 700;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }

        .job-cv-category,
        .job-cv-count,
        .job-cv-score-label {
            color: rgba(232,238,246,0.62);
            font-size: 0.76rem;
        }

        .job-cv-pick {
            display: inline-block;
            margin-left: 0.5rem;
            padding: 0.12rem 0.45rem;
            border-radius: 999px;
            background: rgba(112,190,242,0.16);
            color: #a6d9ff;
            font-size: 0.68rem;
            vertical-align: middle;
            white-space: nowrap;
        }

        .job-cv-score-wrap {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            flex-shrink: 0;
            line-height: 1.25;
        }

        .job-cv-score {
            color: #eaf6ff;
            font-size: 1.45rem;
            font-weight: 700;
        }

        .job-cv-score-empty {
            color: rgba(232,238,246,0.6);
            font-size: 0.76rem;
            text-align: right;
        }

        .job-cv-bar {
            height: 0.45rem;
            margin: 0.95rem 0 0.4rem;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(255,255,255,0.12);
        }

        .job-cv-bar span {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: #80c7f3;
        }

        .job-cv-required {
            margin-top: 0.9rem;
            padding-top: 0.8rem;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        .job-cv-required-heading {
            color: rgba(232,238,246,0.72);
            font-size: 0.76rem;
        }

        .job-cv-required-value {
            margin: 0.2rem 0;
            color: #eaf6ff;
            font-size: 1.05rem;
            font-weight: 700;
        }

        .job-cv-required-detail {
            margin-top: 0.45rem;
            color: rgba(232,238,246,0.78);
            font-size: 0.76rem;
            line-height: 1.4;
            overflow-wrap: anywhere;
        }

        .job-skill-panel.found {
            border-top: 2px solid #61c59a;
        }

        .job-skill-panel.missing {
            border-top: 2px solid #e4b56d;
        }

        .job-skill-heading {
            align-items: center;
            color: #f4f7fb;
            font-size: 0.9rem;
            font-weight: 650;
        }

        .job-skill-heading strong {
            font-size: 1.1rem;
        }

        .job-skill-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.85rem;
        }

        .job-skill-chip {
            padding: 0.3rem 0.55rem;
            border-radius: 0.4rem;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.055);
            color: #e8eef6;
            font-size: 0.8rem;
            line-height: 1.35;
        }

        .job-skill-empty {
            color: rgba(232,238,246,0.62);
            font-size: 0.8rem;
        }

        @media (max-width: 650px) {
            .job-cv-comparison,
            .job-skill-evidence {
                grid-template-columns: 1fr;
            }
        }


        /* Metric cards */
        [data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.03);
            padding: 1rem;
            border-radius: 0.75rem;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.9rem;
        }

        [data-testid="stMetricValue"] {
            font-size: 2rem;
        }

        [data-testid="stSpinner"] p {
            color: #c9d9e8;
            font-size: 0.85rem;
            font-weight: 600;
        }

        button:focus-visible,
        [role="tab"]:focus-visible,
        [role="option"]:focus-visible {
            outline: 2px solid #8ec5f0 !important;
            outline-offset: 2px;
        }

        [data-testid="stTabs"] [role="tab"] {
            font-size: 0.9rem;
            font-weight: 600;
        }

        /* Headings */
        h1 {
            margin-bottom: 0.35rem;
            letter-spacing: -0.025em;
        }

        h2, h3 {
            margin-top: 1.35rem;
            margin-bottom: 0.65rem;
        }

        /* Hide Ctrl + Enter hints */
        [data-testid="InputInstructions"] {
            display: none !important;
        }

        /* Compact status popover button */
        div[data-testid="stPopover"] button {
            min-height: 2.1rem !important;
            padding: 0.25rem 0.7rem !important;
            border-radius: 0.55rem !important;
            background-color: rgba(255, 255, 255, 0.035) !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            box-shadow: none !important;
        }

        div[data-testid="stPopover"] button:hover {
            background-color: rgba(255, 255, 255, 0.065) !important;
            border-color: rgba(255, 255, 255, 0.22) !important;
        }

        div[data-testid="stPopover"] button p {
            font-size: 0.86rem !important;
            font-weight: 600 !important;
        }

        /* Popover dropdown menu */
        div[data-baseweb="popover"] {
            border-radius: 0.65rem !important;
        }

        div[data-baseweb="popover"] ul {
            background-color: #1f2028 !important;
            border-radius: 0.65rem !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            padding: 0.4rem !important;
        }

        div[data-baseweb="popover"] li {
            background-color: transparent !important;
            border-radius: 0.45rem !important;
        }

        div[data-baseweb="popover"] li:hover {
            background-color: rgba(255, 255, 255, 0.08) !important;
        }

        /* Radio options inside popover */
        div[data-testid="stRadio"] label {
            padding: 0.2rem 0rem !important;
        }

        div[data-testid="stRadio"] p {
            font-size: 0.9rem !important;
            font-weight: 500 !important;
        }

        /* Horizontal dividers */
        hr {
            border-color: rgba(255, 255, 255, 0.08) !important;
        }

        /* Icon buttons */
        button[kind="secondary"] {
            border-radius: 0.5rem !important;
        }

        .overview-section-label {
            color: #8ec5f0;
            font-size: 0.66rem;
            font-weight: 750;
            letter-spacing: 0.14em;
            margin-top: 1.7rem;
        }

        .overview-action-title {
            color: #f4f7fb;
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.3;
        }

        .overview-action-meta {
            color: rgba(232,238,246,0.55);
            font-size: 0.86rem;
            line-height: 1.35;
            margin-top: 0.2rem;
        }

        .overview-state {
            color: #dfeaf5;
            font-size: 0.91rem;
            font-weight: 650;
            line-height: 1.35;
        }

        .overview-state.overdue { color: #ff9a9a; }
        .overview-state.today { color: #f4c76e; }

        .overview-row-divider {
            border-top: 1px solid rgba(255,255,255,0.07);
            margin: 0.25rem 0;
        }

        /* The follow-up queue has generous horizontal space, so keep its
           information comfortably readable instead of using table-sized text. */
        div[data-testid="stVerticalBlockBorderWrapper"] .overview-action-title + .overview-action-meta {
            font-size: 0.86rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] button p {
            font-size: 0.86rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
