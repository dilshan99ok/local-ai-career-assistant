import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"


def print_rows(title, query):
    print(f"\n=== {title} ===")

    cursor.execute(query)

    rows = cursor.fetchall()

    if not rows:
        print("No records found.")
        return

    for row in rows:
        print(row)


connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

print_rows(
    "JOBS",
    """
    SELECT id, job_title, domain
    FROM jobs
    ORDER BY id
    """
)

print_rows(
    "TOP DOMAINS",
    """
    SELECT domain, COUNT(*)
    FROM jobs
    GROUP BY domain
    ORDER BY COUNT(*) DESC
    """
)

print_rows(
    "TOP TECHNICAL SKILLS",
    """
    SELECT item_value, COUNT(*)
    FROM job_items
    WHERE item_type = 'technical_skill'
    GROUP BY item_value
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """
)

print_rows(
    "TOP TOOLS / PLATFORMS",
    """
    SELECT item_value, COUNT(*)
    FROM job_items
    WHERE item_type = 'tool_platform'
    GROUP BY item_value
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """
)

print_rows(
    "TOP CERTIFICATIONS",
    """
    SELECT item_value, COUNT(*)
    FROM job_items
    WHERE item_type = 'certification'
    GROUP BY item_value
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """
)

print_rows(
    "TOP RESPONSIBILITIES",
    """
    SELECT item_value, COUNT(*)
    FROM job_items
    WHERE item_type = 'responsibility'
    GROUP BY item_value
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """
)

print_rows(
    "TOP SOFT SKILLS",
    """
    SELECT item_value, COUNT(*)
    FROM job_items
    WHERE item_type = 'soft_skill'
    GROUP BY item_value
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """
)

print_rows(
    "TOP DOMAIN-SPECIFIC SKILLS",
    """
    SELECT item_value, COUNT(*)
    FROM job_items
    WHERE item_type = 'domain_specific_skill'
    GROUP BY item_value
    ORDER BY COUNT(*) DESC
    LIMIT 20
    """
)

print_rows(
    "APPLICATIONS",
    """
    SELECT company,
           job_title,
           domain,
           date_applied,
           follow_up_date,
           current_status
    FROM applications
    ORDER BY date_applied DESC
    """
)

print_rows(
    "APPLICATION SUMMARY",
    """
    SELECT current_status, COUNT(*)
    FROM applications
    GROUP BY current_status
    ORDER BY COUNT(*) DESC
    """
)

print_rows(
    "APPLICATIONS BY DOMAIN",
    """
    SELECT domain, COUNT(*)
    FROM applications
    GROUP BY domain
    ORDER BY COUNT(*) DESC
    """
)

print_rows(
    "FOLLOW UPS REQUIRED",
    """
    SELECT company,
           job_title,
           date_applied,
           follow_up_date,
           current_status
    FROM applications
    WHERE current_status = 'Applied'
      AND follow_up_date IS NOT NULL
      AND follow_up_date != ''
    ORDER BY follow_up_date
    """
)

connection.close()