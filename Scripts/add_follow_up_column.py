import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"


def main():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    try:
        cursor.execute("""
        ALTER TABLE applications
        ADD COLUMN follow_up_date TEXT
        """)
        print("follow_up_date column added successfully.")
    except sqlite3.OperationalError as error:
        if "duplicate column name" in str(error):
            print("follow_up_date column already exists.")
        else:
            raise

    connection.commit()
    connection.close()


if __name__ == "__main__":
    main()