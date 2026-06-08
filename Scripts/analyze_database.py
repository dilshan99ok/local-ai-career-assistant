import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "database" / "career_intelligence.db"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

print("\n=== JOBS ===")

cursor.execute("""
SELECT id, job_title, domain
FROM jobs
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP TECHNICAL SKILLS ===")

cursor.execute("""
SELECT item_value, COUNT(*)
FROM job_items
WHERE item_type = 'technical_skill'
GROUP BY item_value
ORDER BY COUNT(*) DESC
LIMIT 20
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP DOMAINS ===")

cursor.execute("""
SELECT domain, COUNT(*)
FROM jobs
GROUP BY domain
ORDER BY COUNT(*) DESC
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP TOOLS / PLATFORMS ===")

cursor.execute("""
SELECT item_value, COUNT(*)
FROM job_items
WHERE item_type = 'tool_platform'
GROUP BY item_value
ORDER BY COUNT(*) DESC
LIMIT 20
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP CERTIFICATIONS ===")

cursor.execute("""
SELECT item_value, COUNT(*)
FROM job_items
WHERE item_type = 'certification'
GROUP BY item_value
ORDER BY COUNT(*) DESC
LIMIT 20
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP RESPONSIBILITIES ===")

cursor.execute("""
SELECT item_value, COUNT(*)
FROM job_items
WHERE item_type = 'responsibility'
GROUP BY item_value
ORDER BY COUNT(*) DESC
LIMIT 20
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP SOFT SKILLS ===")

cursor.execute("""
SELECT item_value, COUNT(*)
FROM job_items
WHERE item_type = 'soft_skill'
GROUP BY item_value
ORDER BY COUNT(*) DESC
LIMIT 20
""")

for row in cursor.fetchall():
    print(row)

print("\n=== TOP DOMAIN-SPECIFIC SKILLS ===")

cursor.execute("""
SELECT item_value, COUNT(*)
FROM job_items
WHERE item_type = 'domain_specific_skill'
GROUP BY item_value
ORDER BY COUNT(*) DESC
LIMIT 20
""")

for row in cursor.fetchall():
    print(row)

print("\n=== APPLICATIONS ===")

cursor.execute("""
SELECT company,
       job_title,
       domain,
       date_applied,
       current_status
FROM applications
ORDER BY date_applied DESC
""")

for row in cursor.fetchall():
    print(row)

print("\n=== APPLICATION SUMMARY ===")

cursor.execute("""
SELECT current_status, COUNT(*)
FROM applications
GROUP BY current_status
ORDER BY COUNT(*) DESC
""")

for row in cursor.fetchall():
    print(row)

print("\n=== APPLICATIONS BY DOMAIN ===")

cursor.execute("""
SELECT domain, COUNT(*)
FROM applications
GROUP BY domain
ORDER BY COUNT(*) DESC
""")

for row in cursor.fetchall():
    print(row)

connection.close()