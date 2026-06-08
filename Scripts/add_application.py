import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"

VALID_STATUSES = {"Applied", "Interview", "Offer", "Rejected"}


def get_input(prompt_text, required=True):
    value = input(prompt_text).strip()

    if required and not value:
        raise ValueError(f"{prompt_text} cannot be empty.")

    return value

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

def main():
    print("\n=== Add New Job Application ===\n")

    company = get_input("Company: ")
    job_title = get_input("Job title: ")
    domain = get_input("Domain: ", required=False)
    if domain:
        domain = VALID_DOMAINS.get(domain.lower(), domain)
    source_file = get_input("Source file, e.g. job2.json (optional): ", required=False)
    date_applied = get_input("Date applied, e.g. 2026-06-08: ")
    current_status = get_input("Status (Applied / Interview / Offer / Rejected): ")
    notes = get_input("Notes (optional): ", required=False)

    if current_status not in VALID_STATUSES:
        raise ValueError(
            "Invalid status. Use one of: Applied, Interview, Offer, Rejected."
        )

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO applications
        (company, job_title, domain, source_file, date_applied, current_status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company,
            job_title,
            domain,
            source_file,
            date_applied,
            current_status,
            notes,
        ),
    )

    connection.commit()
    connection.close()

    print("\nApplication added successfully.")


if __name__ == "__main__":
    main()