import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"

VALID_STATUSES = {"Applied", "Interview", "Offer", "Rejected"}

VALID_DOMAINS = {
    "it support": "IT Support",
    "network": "Networking",
    "networking": "Networking",
    "cloud": "Cloud",
    "cybersecurity": "Cybersecurity",
    "systems administration": "Systems Administration",
    "data centre": "Data Centre",
    "infrastructure": "Infrastructure",
    "telecommunications": "Telecommunications",
    "other": "Other",
}


def get_input(prompt_text, required=True):
    value = input(prompt_text).strip()

    if required and not value:
        raise ValueError(f"{prompt_text} cannot be empty.")

    return value


def main():
    print("\n=== Add New Job Application ===\n")

    company = get_input("Company: ")
    job_title = get_input("Job title: ")

    domain = ""

    source_file = get_input("Source file, e.g. job2.json (optional): ", required=False)
    date_applied = get_input("Date applied, e.g. 2026-06-08: ")
    follow_up_date = get_input("Follow-up date (optional): ", required=False)

    contact_name = get_input("Contact name (optional): ", required=False)
    contact_number = get_input("Contact number (optional): ", required=False)

    current_status = get_input("Status (Applied / Interview / Offer / Rejected): ")
    notes = get_input("Notes (optional): ", required=False)

    if current_status not in VALID_STATUSES:
        raise ValueError(
            "Invalid status. Use one of: Applied, Interview, Offer, Rejected."
        )

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    import sqlite3
    from pathlib import Path

    import pandas as pd
    import streamlit as st

    BASE_DIR = Path(__file__).resolve().parent.parent
    DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"

    st.set_page_config(
        page_title="Local AI Career Assistant",
        layout="wide"
    )

    st.title("Local AI Career Assistant")
    st.caption("Job description analytics and application follow-up tracker")

    def load_data(query):
        connection = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, connection)
        connection.close()
        return df

    applications_df = load_data("""
    SELECT company,
           job_title,
           domain,
           date_applied,
           follow_up_date,
           current_status,
           notes
           contact_name,
           contact_number,
    FROM applications
    ORDER BY date_applied DESC
    """)

    followups_df = load_data("""
    SELECT company,
           job_title,
           date_applied,
           follow_up_date,
           current_status
           contact_name,
           contact_number,
    FROM applications
    WHERE current_status = 'Applied'
      AND follow_up_date IS NOT NULL
      AND follow_up_date != ''
    ORDER BY follow_up_date
    """)

    domains_df = load_data("""
    SELECT domain, COUNT(*) AS count
    FROM jobs
    GROUP BY domain
    ORDER BY count DESC
    """)

    skills_df = load_data("""
    SELECT item_value AS skill, COUNT(*) AS count
    FROM job_items
    WHERE item_type = 'technical_skill'
    GROUP BY item_value
    ORDER BY count DESC
    LIMIT 20
    """)

    jobs_df = load_data("""
    SELECT id,
           job_title,
           domain,
           source_file,
           created_at
    FROM jobs
    ORDER BY id DESC
    """)

    st.sidebar.title("Navigation")

    page = st.sidebar.radio(
        "Select Page",
        [
            "Dashboard",
            "Applications",
            "Skills",
            "Jobs"
        ]
    )

    if page == "Dashboard":
        total_apps = len(applications_df)
        applied_count = len(applications_df[applications_df["current_status"] == "Applied"])
        rejected_count = len(applications_df[applications_df["current_status"] == "Rejected"])
        pending_follow_up_count = len(followups_df)

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Applications", total_apps)
        col2.metric("Applied", applied_count)
        col3.metric("Rejected", rejected_count)
        col4.metric("Pending Follow-ups", pending_follow_up_count)

        st.header("Pending Follow-ups")

        st.dataframe(
            followups_df,
            use_container_width=True,
            hide_index=True
        )

        st.header("Top Domains")

        st.bar_chart(domains_df.set_index("domain"))


    elif page == "Applications":
        st.header("Application Tracker")

        st.dataframe(
            applications_df,
            use_container_width=True,
            hide_index=True
        )


    elif page == "Skills":
        st.header("Top Technical Skills")

        st.dataframe(
            skills_df,
            use_container_width=True,
            hide_index=True
        )


    elif page == "Jobs":
        st.header("Analyzed Jobs")

        st.dataframe(
            jobs_df,
            use_container_width=True,
            hide_index=True
        )

    connection.commit()
    connection.close()

    print("\nApplication added successfully.")


if __name__ == "__main__":
    main()