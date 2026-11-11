import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"
_SCHEMA_READY = False


SCHEMA_COLUMNS = {
    "jobs": {
        "recruiter_name": "TEXT",
        "parent_company": "TEXT",
        "end_client_name": "TEXT",
        "end_client_industry": "TEXT",
        "posting_type": "TEXT",
        "raw_description": "TEXT",
        "source_url": "TEXT",
        "location": "TEXT",
        "salary_range": "TEXT",
        "work_mode": "TEXT",
        "application_source": "TEXT",
        "content_hash": "TEXT",
        "extraction_model": "TEXT",
        "extraction_version": "TEXT",
        "analyzed_at": "TEXT",
    },
    "applications": {
        "source_url": "TEXT",
        "location": "TEXT",
        "salary_range": "TEXT",
        "work_mode": "TEXT",
        "application_source": "TEXT",
        "resume_version": "TEXT",
        "cover_letter_status": "TEXT",
        "rejected_reason": "TEXT",
        "interview_date": "TEXT",
        "interview_stage": "TEXT",
        "offer_amount": "TEXT",
        "offer_date": "TEXT",
        "contact_email": "TEXT",
        "contact_role": "TEXT",
        "updated_at": "TEXT",
        "resume_version_id": "INTEGER",
        "cover_letter_version_id": "INTEGER",
    },
    "job_skills": {
        "evidence_text": "TEXT",
        "requirement_level": "TEXT",
        "confidence": "REAL",
    },
    "job_certifications": {
        "evidence_text": "TEXT",
        "confidence": "REAL",
    },
}


def initialize_database():
    """Create the current schema and add newer columns without deleting data."""

    global _SCHEMA_READY

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            job_title TEXT,
            domain TEXT,
            source_file TEXT UNIQUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            job_title TEXT NOT NULL,
            domain TEXT,
            source_file TEXT,
            date_applied TEXT,
            current_status TEXT DEFAULT 'Applied',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            follow_up_date TEXT,
            contact_name TEXT,
            contact_number TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_value TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            raw_skill TEXT,
            specific_skill TEXT NOT NULL,
            skill_basket TEXT NOT NULL,
            created_at TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS job_certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            raw_certification TEXT,
            certification_name TEXT NOT NULL,
            certification_short_name TEXT,
            related_basket TEXT NOT NULL,
            requirement_level TEXT,
            created_at TEXT
        )
        """
    )

    for table_name, columns in SCHEMA_COLUMNS.items():
        existing_columns = {
            row[1]
            for row in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            note TEXT DEFAULT ''
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS follow_up_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            scheduled_for TEXT,
            completed_at TEXT,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_extraction_cache (
            content_hash TEXT PRIMARY KEY,
            model TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            extracted_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT NOT NULL,
            resume_text TEXT NOT NULL,
            skills_json TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            source_filename TEXT DEFAULT '',
            source_type TEXT DEFAULT 'Pasted text',
            source_file BLOB,
            target_domain TEXT DEFAULT 'General',
            details_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    resume_profile_columns = {
        "source_filename": "TEXT",
        "source_type": "TEXT",
        "source_file": "BLOB",
        "target_domain": "TEXT DEFAULT 'General'",
        "details_json": "TEXT",
    }
    existing_resume_columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(resume_profiles)").fetchall()
    }
    for column_name, column_type in resume_profile_columns.items():
        if column_name not in existing_resume_columns:
            cursor.execute(
                f"ALTER TABLE resume_profiles ADD COLUMN {column_name} {column_type}"
            )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS skill_normalization_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL UNIQUE,
            canonical_skill TEXT NOT NULL,
            canonical_basket TEXT,
            reviewed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS certification_normalization_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL UNIQUE,
            canonical_name TEXT NOT NULL,
            reviewed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER,
            version_name TEXT NOT NULL,
            content TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'original',
            target_job_id INTEGER,
            change_summary TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cover_letter_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            job_id INTEGER,
            version_name TEXT NOT NULL,
            content TEXT NOT NULL,
            tone TEXT DEFAULT 'professional',
            status TEXT DEFAULT 'Drafted',
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS application_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            job_id INTEGER,
            message_type TEXT NOT NULL,
            subject TEXT DEFAULT '',
            content TEXT NOT NULL,
            status TEXT DEFAULT 'Drafted',
            created_at TEXT NOT NULL
        )
        """
    )

    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(current_status)",
        "CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(date_applied)",
        "CREATE INDEX IF NOT EXISTS idx_applications_follow_up ON applications(follow_up_date)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_domain ON jobs(domain)",
        "CREATE INDEX IF NOT EXISTS idx_job_skills_basket ON job_skills(skill_basket)",
        "CREATE INDEX IF NOT EXISTS idx_job_certifications_name ON job_certifications(certification_short_name)",
        "CREATE INDEX IF NOT EXISTS idx_status_history_application ON application_status_history(application_id)",
        "CREATE INDEX IF NOT EXISTS idx_follow_up_events_application ON follow_up_events(application_id)",
        "CREATE INDEX IF NOT EXISTS idx_resume_versions_job ON resume_versions(target_job_id)",
        "CREATE INDEX IF NOT EXISTS idx_cover_letter_versions_job ON cover_letter_versions(job_id)",
    ):
        cursor.execute(statement)

    cursor.execute(
        """
        INSERT INTO application_status_history
        (application_id, status, changed_at, note)
        SELECT a.id, a.current_status, COALESCE(a.created_at, ?), 'Imported from existing data'
        FROM applications a
        WHERE NOT EXISTS (
            SELECT 1
            FROM application_status_history h
            WHERE h.application_id = a.id
        )
        """,
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
    )
    cursor.execute(
        """
        INSERT INTO follow_up_events
        (application_id, event_type, scheduled_for, completed_at, note, created_at)
        SELECT a.id, 'scheduled', a.follow_up_date, '',
               'Imported from existing data',
               COALESCE(a.created_at, ?)
        FROM applications a
        WHERE a.follow_up_date IS NOT NULL
          AND a.follow_up_date != ''
          AND NOT EXISTS (
              SELECT 1
              FROM follow_up_events f
              WHERE f.application_id = a.id
          )
        """,
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
    )

    connection.commit()
    connection.close()
    _SCHEMA_READY = True


def get_connection():
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        initialize_database()

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def load_data(query, params=None):
    if params is None:
        params = ()

    connection = get_connection()
    df = pd.read_sql_query(query, connection, params=params)
    connection.close()

    return df


def _timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_job_detail_df(job_id):
    return load_data(
        "SELECT * FROM jobs WHERE id = ?",
        params=(job_id,),
    )


def get_job_skills_for_job_df(job_id):
    return load_data(
        """
        SELECT raw_skill, specific_skill, skill_basket,
               evidence_text, requirement_level, confidence, created_at
        FROM job_skills
        WHERE job_id = ?
        ORDER BY skill_basket, specific_skill
        """,
        params=(job_id,),
    )


def get_job_certifications_for_job_df(job_id):
    return load_data(
        """
        SELECT raw_certification, certification_name,
               certification_short_name, related_basket,
               requirement_level, created_at
        FROM job_certifications
        WHERE job_id = ?
        ORDER BY certification_name
        """,
        params=(job_id,),
    )


def get_applications_for_job_df(source_file):
    return load_data(
        """
        SELECT id, company, job_title, current_status, date_applied,
               follow_up_date, contact_name, contact_email
        FROM applications
        WHERE source_file = ?
        ORDER BY id DESC
        """,
        params=(source_file,),
    )


def get_duplicate_applications(company, job_title, source_url=""):
    filters = ["(LOWER(company) = LOWER(?) AND LOWER(job_title) = LOWER(?))"]
    params = [company.strip(), job_title.strip()]
    if source_url.strip():
        filters.append("(source_url != '' AND source_url = ?)")
        params.append(source_url.strip())

    return load_data(
        f"""
        SELECT id, company, job_title, current_status, date_applied, source_url
        FROM applications
        WHERE {' OR '.join(filters)}
        ORDER BY id DESC
        """,
        params=tuple(params),
    )


def get_application_status_history_df(application_id):
    return load_data(
        """
        SELECT status, changed_at, note
        FROM application_status_history
        WHERE application_id = ?
        ORDER BY changed_at DESC, id DESC
        """,
        params=(application_id,),
    )


def get_follow_up_events_df(application_id):
    return load_data(
        """
        SELECT event_type, scheduled_for, completed_at, note, created_at
        FROM follow_up_events
        WHERE application_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        params=(application_id,),
    )


def record_status_change(application_id, status, note="", connection=None):
    owns_connection = connection is None
    connection = connection or get_connection()
    connection.execute(
        """
        INSERT INTO application_status_history
        (application_id, status, changed_at, note)
        VALUES (?, ?, ?, ?)
        """,
        (application_id, status, _timestamp(), note or ""),
    )
    if owns_connection:
        connection.commit()
        connection.close()


def record_follow_up_event(
    application_id,
    event_type,
    scheduled_for="",
    completed_at="",
    note="",
    connection=None,
):
    owns_connection = connection is None
    connection = connection or get_connection()
    connection.execute(
        """
        INSERT INTO follow_up_events
        (application_id, event_type, scheduled_for, completed_at, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            event_type,
            str(scheduled_for or ""),
            str(completed_at or ""),
            note or "",
            _timestamp(),
        ),
    )
    if owns_connection:
        connection.commit()
        connection.close()


def get_cached_extraction(content_hash):
    connection = get_connection()
    row = connection.execute(
        """
        SELECT extracted_json
        FROM ai_extraction_cache
        WHERE content_hash = ?
        """,
        (content_hash,),
    ).fetchone()
    connection.close()

    if not row:
        return None

    try:
        value = json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return None

    return value if isinstance(value, dict) else None


def save_cached_extraction(content_hash, model, extracted_data, schema_version="1"):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO ai_extraction_cache
        (content_hash, model, schema_version, extracted_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(content_hash) DO UPDATE SET
            model = excluded.model,
            schema_version = excluded.schema_version,
            extracted_json = excluded.extracted_json,
            created_at = excluded.created_at
        """,
        (
            content_hash,
            model,
            schema_version,
            json.dumps(extracted_data),
            _timestamp(),
        ),
    )
    connection.commit()
    connection.close()


def get_status_summary_df():
    return load_data(
        """
        SELECT current_status AS status, COUNT(*) AS count
        FROM applications
        GROUP BY current_status
        ORDER BY count DESC, status
        """
    )


def get_application_trend_df():
    return load_data(
        """
        SELECT substr(date_applied, 1, 7) AS month, COUNT(*) AS count
        FROM applications
        WHERE date_applied IS NOT NULL AND date_applied != ''
        GROUP BY substr(date_applied, 1, 7)
        ORDER BY month
        """
    )


def get_resume_profiles_df():
    return load_data(
        """
        SELECT id, profile_name, resume_text, skills_json, is_active,
               source_filename, source_type, target_domain, details_json, created_at, updated_at
        FROM resume_profiles
        ORDER BY is_active DESC, target_domain, profile_name
        """
    )


def get_resume_source_file(profile_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT source_filename, source_file FROM resume_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        return (row[0], bytes(row[1]) if row[1] is not None else None) if row else ("", None)
    finally:
        connection.close()


def attach_resume_source_file(profile_id, filename, data):
    connection = get_connection()
    try:
        with connection:
            connection.execute(
                "UPDATE resume_profiles SET source_filename = ?, source_type = ?, source_file = ?, updated_at = ? WHERE id = ?",
                (filename, Path(filename).suffix.upper().lstrip("."), data, _timestamp(), profile_id),
            )
    finally:
        connection.close()


def save_resume_profile(
    profile_name,
    resume_text,
    skills,
    profile_id=None,
    source_filename=None,
    source_type=None,
    source_file=None,
    details=None,
    target_domain="General",
    make_active=False,
):
    connection = get_connection()
    now = _timestamp()
    activate = bool(make_active) or connection.execute(
        "SELECT 1 FROM resume_profiles WHERE is_active = 1 LIMIT 1"
    ).fetchone() is None
    if activate:
        connection.execute("UPDATE resume_profiles SET is_active = 0 WHERE is_active = 1")

    if profile_id:
        updates = ["profile_name = ?", "resume_text = ?", "skills_json = ?", "target_domain = ?", "updated_at = ?"]
        values = [profile_name, resume_text, json.dumps(skills), target_domain, now]
        if activate:
            updates.append("is_active = 1")
        if source_filename is not None:
            updates.append("source_filename = ?")
            values.append(source_filename)
        if source_type is not None:
            updates.append("source_type = ?")
            values.append(source_type)
        if source_file is not None:
            updates.append("source_file = ?")
            values.append(source_file)
        if details is not None:
            updates.append("details_json = ?")
            values.append(json.dumps(details))
        values.append(profile_id)
        connection.execute(
            f"UPDATE resume_profiles SET {', '.join(updates)} WHERE id = ?", values
        )
    else:
        cursor = connection.execute(
            """
            INSERT INTO resume_profiles
            (profile_name, resume_text, skills_json, is_active, source_filename,
             source_type, source_file, target_domain, details_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_name,
                resume_text,
                json.dumps(skills),
                int(activate),
                source_filename or "",
                source_type or "Pasted text",
                source_file,
                target_domain,
                json.dumps(details or {}),
                now,
                now,
            ),
        )
        profile_id = cursor.lastrowid

    connection.commit()
    connection.close()
    return profile_id


def set_active_resume_profile(profile_id):
    connection = get_connection()
    connection.execute("UPDATE resume_profiles SET is_active = 0")
    connection.execute(
        "UPDATE resume_profiles SET is_active = 1, updated_at = ? WHERE id = ?",
        (_timestamp(), profile_id),
    )
    connection.commit()
    connection.close()


def delete_resume_profile(profile_id):
    """Remove a base CV while keeping its job-specific drafts and application links."""
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT is_active FROM resume_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if row is None:
            return False
        with connection:
            connection.execute(
                "UPDATE resume_versions SET profile_id = NULL WHERE profile_id = ?",
                (profile_id,),
            )
            connection.execute("DELETE FROM resume_profiles WHERE id = ?", (profile_id,))
            if row[0]:
                replacement = connection.execute(
                    "SELECT id FROM resume_profiles ORDER BY updated_at DESC, id DESC LIMIT 1"
                ).fetchone()
                if replacement:
                    connection.execute(
                        "UPDATE resume_profiles SET is_active = 1 WHERE id = ?",
                        (replacement[0],),
                    )
        return True
    finally:
        connection.close()


def import_applications_dataframe(dataframe):
    """Import basic application rows from a CSV-backed DataFrame."""

    required_columns = {"company", "job_title"}
    missing = required_columns - {
        str(column).lower().strip() for column in dataframe.columns
    }
    if missing:
        raise ValueError(
            "CSV must include these columns: " + ", ".join(sorted(missing))
        )

    normalized = dataframe.copy()
    normalized.columns = [str(column).lower().strip() for column in normalized.columns]
    connection = get_connection()
    imported = 0
    skipped = 0

    def value(row, key):
        item = row.get(key, "")
        return "" if pd.isna(item) else str(item).strip()

    for _, row in normalized.iterrows():
        company = value(row, "company")
        job_title = value(row, "job_title")
        if not company or not job_title:
            skipped += 1
            continue

        existing = connection.execute(
            """
            SELECT id FROM applications
            WHERE LOWER(company) = LOWER(?)
              AND LOWER(job_title) = LOWER(?)
              AND date_applied = ?
            """,
            (company, job_title, value(row, "date_applied")),
        ).fetchone()
        if existing:
            skipped += 1
            continue

        source_file = f"import_{uuid.uuid4().hex}"
        created_at = _timestamp()
        connection.execute(
            """
            INSERT INTO jobs
            (company, job_title, domain, source_file, created_at, source_url,
             location, salary_range, work_mode, application_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                job_title,
                value(row, "domain"),
                source_file,
                created_at,
                value(row, "source_url"),
                value(row, "location"),
                value(row, "salary_range"),
                value(row, "work_mode"),
                value(row, "application_source"),
            ),
        )
        connection.execute(
            """
            INSERT INTO applications
            (company, job_title, domain, source_file, date_applied,
             follow_up_date, contact_name, contact_number, contact_email,
             source_url, location, salary_range, work_mode,
             application_source, current_status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company,
                job_title,
                value(row, "domain"),
                source_file,
                value(row, "date_applied"),
                value(row, "follow_up_date"),
                value(row, "contact_name"),
                value(row, "contact_number"),
                value(row, "contact_email"),
                value(row, "source_url"),
                value(row, "location"),
                value(row, "salary_range"),
                value(row, "work_mode"),
                value(row, "application_source"),
                value(row, "current_status") or "Applied",
                value(row, "notes"),
                created_at,
            ),
        )
        application_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        record_status_change(application_id, value(row, "current_status") or "Applied", connection=connection)
        imported += 1

    connection.commit()
    connection.close()
    return imported, skipped


# ---------------------------------------------------------------------
# Application Data
# ---------------------------------------------------------------------

def get_applications_df():
    return load_data(
        """
        SELECT
            id,
            company,
            job_title,
            domain,
            source_file,
            date_applied,
            follow_up_date,
            contact_name,
            contact_number,
            contact_email,
            contact_role,
            source_url,
            location,
            salary_range,
            work_mode,
            application_source,
            resume_version,
            cover_letter_status,
            rejected_reason,
            interview_date,
            interview_stage,
            offer_amount,
            offer_date,
            current_status,
            notes,
            created_at,
            updated_at
        FROM applications
        ORDER BY date_applied DESC, id DESC
        """
    )


def get_dashboard_followups_df():
    return load_data(
        """
        SELECT
            a.id,
            a.company,
            a.job_title,
            a.source_file,
            j.id AS job_id,
            follow_up_date,
            contact_name,
            contact_number,
            current_status,
            notes
        FROM applications a
        LEFT JOIN jobs j ON j.source_file = a.source_file
        WHERE a.follow_up_date IS NOT NULL
          AND a.follow_up_date != ''
          AND LOWER(a.follow_up_date) != 'none'
          AND a.current_status NOT IN ('Rejected', 'Offer', 'Withdrawn', 'Archived')
        ORDER BY a.follow_up_date ASC, a.id DESC
        """
    )


def get_domains_df():
    return load_data(
        """
        SELECT
            domain,
            COUNT(*) AS count
        FROM applications
        WHERE domain IS NOT NULL
          AND domain != ''
        GROUP BY domain
        ORDER BY count DESC
        """
    )


def get_jobs_df():
    return load_data(
        """
        SELECT
            id,
            company,
            recruiter_name,
            parent_company,
            end_client_name,
            end_client_industry,
            posting_type,
            job_title,
            domain,
            source_file,
            created_at,
            raw_description,
            source_url,
            location,
            salary_range,
            work_mode,
            application_source,
            content_hash,
            extraction_model,
            extraction_version,
            analyzed_at
        FROM jobs
        ORDER BY id DESC
        """
    )


# ---------------------------------------------------------------------
# Legacy Skills Query
# ---------------------------------------------------------------------

def get_skills_df():
    return load_data(
        """
        SELECT
            item_value AS skill,
            COUNT(*) AS count
        FROM job_items
        WHERE item_type = 'technical_skill'
        GROUP BY item_value
        ORDER BY count DESC
        LIMIT 20
        """
    )


# ---------------------------------------------------------------------
# Structured Skills / Certifications Queries
# ---------------------------------------------------------------------

def get_skill_basket_summary_df():
    return load_data(
        """
        SELECT
            skill_basket AS "Skill Basket",
            COUNT(*) AS "Count"
        FROM job_skills
        GROUP BY skill_basket
        ORDER BY COUNT(*) DESC, skill_basket ASC
        """
    )


def get_specific_skills_df():
    return load_data(
        """
        SELECT
            skill_basket AS "Skill Basket",
            specific_skill AS "Specific Skill",
            COUNT(*) AS "Count"
        FROM job_skills
        GROUP BY skill_basket, specific_skill
        ORDER BY skill_basket ASC, COUNT(*) DESC, specific_skill ASC
        """
    )


def get_top_skills_df(limit=6):
    return load_data(
        """
        SELECT
            specific_skill AS skill,
            skill_basket AS basket,
            COUNT(*) AS count
        FROM job_skills
        WHERE skill_basket NOT IN (
            'Documentation & Communication',
            'Service Desk & ITSM',
            'AI & Digital Productivity'
        )
        AND specific_skill NOT IN (
            'Customer Service',
            'Documentation',
            'Knowledge Base Documentation',
            'Service Request Management',
            'Incident Management',
            'Ticketing',
            'Escalation Management',
            'Stakeholder Communication'
        )
        GROUP BY specific_skill, skill_basket
        ORDER BY COUNT(*) DESC, specific_skill ASC
        LIMIT ?
        """,
        params=(limit,),
    )


def get_top_skill_areas_df(limit=6):
    return load_data(
        """
        SELECT
            skill_basket AS skill_area,
            COUNT(DISTINCT job_id) AS job_count
        FROM job_skills
        WHERE skill_basket NOT IN (
            'Documentation & Communication',
            'Service Desk & ITSM',
            'AI & Digital Productivity'
        )
        GROUP BY skill_basket
        ORDER BY COUNT(DISTINCT job_id) DESC, skill_basket ASC
        LIMIT ?
        """,
        params=(limit,),
    )


def get_certifications_df():
    return load_data(
        """
        SELECT
            certification_short_name AS "Certification",
            certification_name AS "Certification Name",
            related_basket AS "Related Basket",
            requirement_level AS "Requirement Level",
            COUNT(*) AS "Count"
        FROM job_certifications
        GROUP BY
            certification_short_name,
            certification_name,
            related_basket,
            requirement_level
        ORDER BY COUNT(*) DESC, certification_short_name ASC, related_basket ASC
        """
    )


def get_skill_demand_rows_df():
    return load_data(
        """
        SELECT
            js.id,
            js.job_id,
            js.raw_skill,
            js.specific_skill,
            js.skill_basket,
            js.evidence_text,
            js.requirement_level,
            js.confidence,
            js.created_at,
            j.company,
            j.job_title,
            j.domain,
            j.created_at AS job_created_at
        FROM job_skills js
        LEFT JOIN jobs j ON j.id = js.job_id
        ORDER BY js.created_at DESC, js.id DESC
        """
    )


def get_certification_demand_rows_df():
    return load_data(
        """
        SELECT
            jc.id,
            jc.job_id,
            jc.raw_certification,
            jc.certification_name,
            jc.certification_short_name,
            jc.related_basket,
            jc.requirement_level,
            jc.evidence_text,
            jc.confidence,
            jc.created_at,
            j.company,
            j.job_title,
            j.domain,
            j.created_at AS job_created_at
        FROM job_certifications jc
        LEFT JOIN jobs j ON j.id = jc.job_id
        ORDER BY jc.created_at DESC, jc.id DESC
        """
    )


def get_skill_normalization_rules_df():
    return load_data(
        """
        SELECT alias, canonical_skill, canonical_basket, reviewed, created_at
        FROM skill_normalization_rules
        ORDER BY reviewed ASC, alias ASC
        """
    )


def save_skill_normalization_rule(alias, canonical_skill, canonical_basket=""):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO skill_normalization_rules
        (alias, canonical_skill, canonical_basket, reviewed, created_at)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(alias) DO UPDATE SET
            canonical_skill = excluded.canonical_skill,
            canonical_basket = excluded.canonical_basket,
            reviewed = 1
        """,
        (alias.strip(), canonical_skill.strip(), canonical_basket.strip(), _timestamp()),
    )
    connection.commit()
    connection.close()


def get_certification_normalization_rules_df():
    return load_data(
        """
        SELECT alias, canonical_name, reviewed, created_at
        FROM certification_normalization_rules
        ORDER BY reviewed ASC, alias ASC
        """
    )


def save_certification_normalization_rule(alias, canonical_name):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO certification_normalization_rules
        (alias, canonical_name, reviewed, created_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(alias) DO UPDATE SET
            canonical_name = excluded.canonical_name,
            reviewed = 1
        """,
        (alias.strip(), canonical_name.strip(), _timestamp()),
    )
    connection.commit()
    connection.close()


def get_resume_versions_df(profile_id=None):
    query = """
        SELECT rv.id, rv.profile_id, rv.version_name, rv.content, rv.source_type,
               rv.target_job_id, rv.change_summary, rv.created_at,
               rp.profile_name AS source_profile_name, rp.target_domain
        FROM resume_versions rv
        LEFT JOIN resume_profiles rp ON rp.id = rv.profile_id
    """
    params = ()
    if profile_id is not None:
        query += " WHERE rv.profile_id = ?"
        params = (profile_id,)
    query += " ORDER BY rv.created_at DESC, rv.id DESC"
    return load_data(query, params=params)


def save_resume_version(
    version_name,
    content,
    profile_id=None,
    source_type="original",
    target_job_id=None,
    change_summary="",
    application_id=None,
):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO resume_versions
        (profile_id, version_name, content, source_type, target_job_id, change_summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile_id,
            version_name.strip(),
            content,
            source_type,
            target_job_id,
            change_summary.strip(),
            _timestamp(),
        ),
    )
    version_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    if application_id:
        connection.execute(
            """
            UPDATE applications
            SET resume_version_id = ?, resume_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (version_id, version_name.strip(), _timestamp(), application_id),
        )
    connection.commit()
    connection.close()
    return version_id


def get_cover_letter_versions_df(job_id=None, application_id=None):
    filters = []
    params = []
    if job_id is not None:
        filters.append("job_id = ?")
        params.append(job_id)
    if application_id is not None:
        filters.append("application_id = ?")
        params.append(application_id)

    query = """
        SELECT id, application_id, job_id, version_name, content,
               tone, status, created_at
        FROM cover_letter_versions
    """
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY created_at DESC, id DESC"
    return load_data(query, params=tuple(params))


def get_application_messages_df(job_id=None, application_id=None, message_type=None):
    filters = []
    params = []
    if job_id is not None:
        filters.append("job_id = ?")
        params.append(job_id)
    if application_id is not None:
        filters.append("application_id = ?")
        params.append(application_id)
    if message_type is not None:
        filters.append("message_type = ?")
        params.append(message_type)

    query = """
        SELECT id, application_id, job_id, message_type, subject,
               content, status, created_at
        FROM application_messages
    """
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY created_at DESC, id DESC"
    return load_data(query, params=tuple(params))


def save_application_message(
    content,
    message_type="follow_up_email",
    subject="",
    job_id=None,
    application_id=None,
    status="Drafted",
):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO application_messages
        (application_id, job_id, message_type, subject, content, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            job_id,
            message_type,
            subject.strip(),
            content,
            status,
            _timestamp(),
        ),
    )
    message_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.commit()
    connection.close()
    return message_id


def save_cover_letter_version(
    version_name,
    content,
    job_id=None,
    application_id=None,
    tone="professional",
    status="Drafted",
):
    connection = get_connection()
    connection.execute(
        """
        INSERT INTO cover_letter_versions
        (application_id, job_id, version_name, content, tone, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            job_id,
            version_name.strip(),
            content,
            tone,
            status,
            _timestamp(),
        ),
    )
    version_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    if application_id:
        connection.execute(
            """
            UPDATE applications
            SET cover_letter_version_id = ?, cover_letter_status = ?, updated_at = ?
            WHERE id = ?
            """,
            (version_id, status, _timestamp(), application_id),
        )
    connection.commit()
    connection.close()
    return version_id


# ---------------------------------------------------------------------
# Application Update Helpers
# ---------------------------------------------------------------------

def update_application(
    application_id,
    company,
    job_title,
    domain,
    date_applied,
    follow_up_date,
    contact_name,
    contact_number,
    current_status,
    notes,
    contact_email="",
    contact_role="",
    source_url="",
    location="",
    salary_range="",
    work_mode="",
    application_source="",
    resume_version="",
    cover_letter_status="Not started",
    rejected_reason="",
    interview_date="",
    interview_stage="",
    offer_amount="",
    offer_date="",
):
    connection = get_connection()
    cursor = connection.cursor()

    company = company.strip()
    job_title = job_title.strip()
    domain = domain.strip()
    contact_name = contact_name.strip()
    contact_number = contact_number.strip()
    contact_email = contact_email.strip()
    contact_role = contact_role.strip()
    source_url = source_url.strip()
    location = location.strip()
    salary_range = salary_range.strip()
    work_mode = work_mode.strip()
    application_source = application_source.strip()
    resume_version = resume_version.strip()
    cover_letter_status = cover_letter_status.strip()
    rejected_reason = rejected_reason.strip()
    interview_date = str(interview_date or "").strip()
    interview_stage = interview_stage.strip()
    offer_amount = offer_amount.strip()
    offer_date = str(offer_date or "").strip()
    current_status = current_status.strip()
    notes = notes.strip()

    cursor.execute(
        """
        SELECT source_file
        FROM applications
        WHERE id = ?
        """,
        (application_id,),
    )

    result = cursor.fetchone()
    source_file = result[0] if result else None

    previous_status_row = cursor.execute(
        "SELECT current_status, follow_up_date FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
    previous_status = previous_status_row[0] if previous_status_row else ""
    previous_follow_up = previous_status_row[1] if previous_status_row else ""
    new_follow_up = str(follow_up_date) if follow_up_date else ""

    cursor.execute(
        """
        UPDATE applications
        SET company = ?,
            job_title = ?,
            domain = ?,
            date_applied = ?,
            follow_up_date = ?,
            contact_name = ?,
            contact_number = ?,
            contact_email = ?,
            contact_role = ?,
            source_url = ?,
            location = ?,
            salary_range = ?,
            work_mode = ?,
            application_source = ?,
            resume_version = ?,
            cover_letter_status = ?,
            rejected_reason = ?,
            interview_date = ?,
            interview_stage = ?,
            offer_amount = ?,
            offer_date = ?,
            current_status = ?,
            notes = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            company,
            job_title,
            domain,
            str(date_applied),
            new_follow_up,
            contact_name,
            contact_number,
            contact_email,
            contact_role,
            source_url,
            location,
            salary_range,
            work_mode,
            application_source,
            resume_version,
            cover_letter_status,
            rejected_reason,
            interview_date,
            interview_stage,
            offer_amount,
            offer_date,
            current_status,
            notes,
            _timestamp(),
            application_id,
        ),
    )

    if previous_status != current_status:
        record_status_change(application_id, current_status, connection=connection)

    if previous_follow_up != new_follow_up:
        if new_follow_up:
            event_type = "rescheduled" if previous_follow_up else "scheduled"
            record_follow_up_event(
                application_id,
                event_type=event_type,
                scheduled_for=new_follow_up,
                connection=connection,
            )
        else:
            record_follow_up_event(
                application_id,
                event_type="cleared",
                completed_at=_timestamp(),
                connection=connection,
            )

    if source_file:
        cursor.execute(
            """
            UPDATE jobs
            SET company = ?,
                job_title = ?,
                domain = ?,
                source_url = ?,
                location = ?,
                salary_range = ?,
                work_mode = ?,
                application_source = ?
            WHERE source_file = ?
            """,
            (
                company,
                job_title,
                domain,
                source_url,
                location,
                salary_range,
                work_mode,
                application_source,
                source_file,
            ),
        )

    connection.commit()
    connection.close()


def update_application_status(application_id, current_status):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE applications
        SET current_status = ?
        WHERE id = ?
        """,
        (
            current_status.strip(),
            application_id,
        ),
    )

    record_status_change(application_id, current_status.strip(), connection=connection)

    connection.commit()
    connection.close()


def clear_application_follow_up(application_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE applications
        SET follow_up_date = ''
        WHERE id = ?
        """,
        (application_id,),
    )

    record_follow_up_event(
        application_id,
        event_type="cleared",
        completed_at=_timestamp(),
        connection=connection,
    )

    connection.commit()
    connection.close()


def extend_application_follow_up(application_id, days=7):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT follow_up_date
        FROM applications
        WHERE id = ?
        """,
        (application_id,),
    )

    result = cursor.fetchone()

    if not result or not result[0]:
        connection.close()
        return

    current_follow_up_date = str(result[0]).strip()

    try:
        parsed_date = datetime.strptime(current_follow_up_date, "%Y-%m-%d").date()
    except ValueError:
        connection.close()
        return

    new_follow_up_date = parsed_date + timedelta(days=days)

    cursor.execute(
        """
        UPDATE applications
        SET follow_up_date = ?
        WHERE id = ?
        """,
        (
            str(new_follow_up_date),
            application_id,
        ),
    )

    record_follow_up_event(
        application_id,
        event_type="rescheduled",
        scheduled_for=new_follow_up_date,
        connection=connection,
    )

    connection.commit()
    connection.close()


# ---------------------------------------------------------------------
# Delete Helpers
# ---------------------------------------------------------------------

def delete_application(application_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT source_file
        FROM applications
        WHERE id = ?
        """,
        (application_id,),
    )

    result = cursor.fetchone()
    source_file = result[0] if result else None

    cursor.execute(
        """
        DELETE FROM applications
        WHERE id = ?
        """,
        (application_id,),
    )

    if source_file:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM applications
            WHERE source_file = ?
            """,
            (source_file,),
        )

        remaining_applications = cursor.fetchone()[0]

        if remaining_applications == 0:
            cursor.execute(
                """
                SELECT id
                FROM jobs
                WHERE source_file = ?
                """,
                (source_file,),
            )

            job_ids = [row[0] for row in cursor.fetchall()]

            for job_id in job_ids:
                cursor.execute(
                    """
                    DELETE FROM job_items
                    WHERE job_id = ?
                    """,
                    (job_id,),
                )

                cursor.execute(
                    """
                    DELETE FROM job_skills
                    WHERE job_id = ?
                    """,
                    (job_id,),
                )

                cursor.execute(
                    """
                    DELETE FROM job_certifications
                    WHERE job_id = ?
                    """,
                    (job_id,),
                )

            cursor.execute(
                """
                DELETE FROM jobs
                WHERE source_file = ?
                """,
                (source_file,),
            )

    connection.commit()
    connection.close()
