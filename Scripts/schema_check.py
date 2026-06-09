import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

cursor.execute("""
UPDATE applications
SET follow_up_date = '2026-06-15'
WHERE company = 'Endava'
""")

connection.commit()
connection.close()

print("Follow-up date updated.")