import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"


def update_database():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS applications")

    cursor.execute("""
    CREATE TABLE applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        job_title TEXT NOT NULL,
        domain TEXT,
        source_file TEXT,
        date_applied TEXT,
        current_status TEXT DEFAULT 'Applied'
            CHECK(current_status IN ('Applied', 'Interview', 'Offer', 'Rejected')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    connection.commit()
    connection.close()

    print("Applications table reset and created successfully.")


if __name__ == "__main__":
    update_database()