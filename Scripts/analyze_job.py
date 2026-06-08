import json
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "Data" / "raw-job-descriptions"
OUTPUT_DIR = BASE_DIR / "Data" / "processed"

MODEL_NAME = "qwen2.5:7b"
OLLAMA_URL = "http://localhost:11434/api/generate"


def build_prompt(job_description: str) -> str:
    return f"""
Analyze the job description below and return ONLY valid JSON using this structure:

{{
  "job_title": "",
  "domain": "",
  "technical_skills": [],
  "soft_skills": [],
  "tools_platforms": [],
  "certifications": [],
  "domain_specific_skills": [],
  "responsibilities": []
}}

Rules:
- Return JSON only.
- Do not include explanations before or after the JSON.
- Use the exact field names shown in the schema.
- Keep all values concise and suitable for database storage.
- If a field is not mentioned, return an empty array or empty string.
- The domain must be one of: IT Support, Networking, Cloud, Cybersecurity, Systems Administration, Data Centre, Infrastructure, Telecommunications, Other.
- Select only one best-matching domain.

Classification rules:
- technical_skills should include general technical competencies, methods, and troubleshooting abilities.
- soft_skills should include human/interpersonal skills such as communication, teamwork, customer service, problem-solving, leadership, and time management.
- tools_platforms should include named products, systems, software, operating systems, cloud platforms, ticketing tools, vendor technologies, and management tools.
- certifications should include every certification, qualification, certificate, accreditation program, or certification name explicitly mentioned in the job description.
- domain_specific_skills should include concise skill labels that are strongly linked to the selected domain.
- responsibilities should include actual duties, tasks, or work activities required in the role.

Formatting rules:
- Break combined skills into separate concise items where possible.
- Do not place job duties, tasks, or activities in technical_skills.
- Do not copy long responsibility sentences into technical_skills or domain_specific_skills.
- Convert role-specific duties into concise domain-specific skill labels where appropriate.
- Keep responsibilities as short action-based statements.
- Avoid duplicate items across fields.
- Do not infer skills that are not clearly stated or strongly implied in the job description.
- Do not include company benefits, salary details, culture statements, or generic equal-opportunity text.

Job description:
{job_description}
"""


def analyze_job(input_file: Path) -> dict:
    job_description = input_file.read_text(encoding="utf-8").strip()

    if not job_description:
        raise ValueError(f"{input_file.name} is empty.")

    if len(job_description) < 100:
        raise ValueError(f"{input_file.name} appears too short to analyze reliably.")

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": build_prompt(job_description),
            "stream": False,
        },
        timeout=300,
    )

    response.raise_for_status()

    raw_output = response.json()["response"].strip()

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        print(f"\nInvalid JSON returned for: {input_file.name}")
        print(raw_output)
        raise


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    txt_files = list(INPUT_DIR.glob("*.txt"))

    if not txt_files:
        print("No .txt job descriptions found.")
        return

    for input_file in txt_files:
        output_file = OUTPUT_DIR / f"{input_file.stem}.json"

        if output_file.exists():
            print(f"Skipping already processed file: {input_file.name}")
            continue

        print(f"Analyzing: {input_file.name}")

        try:
            extracted_data = analyze_job(input_file)
        except Exception as error:
            print(f"Failed to analyze {input_file.name}: {error}")
            continue

        output_file.write_text(
            json.dumps(extracted_data, indent=2),
            encoding="utf-8",
        )

        print(f"Saved: {output_file.name}")

    print("Batch analysis completed.")

if __name__ == "__main__":
    main()