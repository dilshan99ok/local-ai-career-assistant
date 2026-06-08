import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"
JSON_DIR = BASE_DIR / "Data" / "processed"


def insert_items(cursor, job_id, item_type, items):
    for item in items:
        cursor.execute(
            """
            INSERT INTO job_items (job_id, item_type, item_value)
            VALUES (?, ?, ?)
            """,
            (job_id, item_type, item)
        )


def main():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    json_files = list(JSON_DIR.glob("*.json"))

    if not json_files:
        print("No JSON files found.")
        return

    for json_file in json_files:

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            cursor.execute(
                """
                INSERT INTO jobs
                (job_title, domain, source_file)
                VALUES (?, ?, ?)
                """,
                (
                    data.get("job_title", ""),
                    data.get("domain", ""),
                    json_file.name
                )
            )

            job_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            print(f"Skipping already imported file: {json_file.name}")
            continue

        insert_items(
            cursor,
            job_id,
            "technical_skill",
            data.get("technical_skills", [])
        )

        insert_items(
            cursor,
            job_id,
            "soft_skill",
            data.get("soft_skills", [])
        )

        insert_items(
            cursor,
            job_id,
            "tool_platform",
            data.get("tools_platforms", [])
        )

        insert_items(
            cursor,
            job_id,
            "certification",
            data.get("certifications", [])
        )

        insert_items(
            cursor,
            job_id,
            "domain_specific_skill",
            data.get("domain_specific_skills", [])
        )

        insert_items(
            cursor,
            job_id,
            "responsibility",
            data.get("responsibilities", [])
        )

        print(f"Imported: {json_file.name}")

    connection.commit()
    connection.close()

    print("Import completed.")


if __name__ == "__main__":
    main()