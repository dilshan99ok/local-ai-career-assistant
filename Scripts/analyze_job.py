import json
from pathlib import Path

from Scripts.ai_provider import OpenAIProvider
from Scripts.prompt_loader import build_extraction_prompt

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_DIR = BASE_DIR / "Data" / "raw-job-descriptions"
OUTPUT_DIR = BASE_DIR / "Data" / "processed"

def build_prompt(job_description: str) -> str:
    return build_extraction_prompt(job_description)


def analyze_job(input_file: Path, provider: OpenAIProvider | None = None) -> dict:
    job_description = input_file.read_text(encoding="utf-8").strip()

    if not job_description:
        raise ValueError(f"{input_file.name} is empty.")

    if len(job_description) < 100:
        raise ValueError(f"{input_file.name} appears too short to analyze reliably.")

    provider = provider or OpenAIProvider()
    extracted_data = provider.extract_job_data(build_prompt(job_description))

    # Safety defaults so downstream scripts do not break
    expected_schema = {
        "company": "",
        "job_title": "",
        "domain": "",
        "technical_skills": [],
        "soft_skills": [],
        "tools_platforms": [],
        "certifications": [],
        "domain_specific_skills": [],
        "responsibilities": [],
    }

    for key, default_value in expected_schema.items():
        extracted_data.setdefault(key, default_value)

    return extracted_data


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    txt_files = list(INPUT_DIR.glob("*.txt"))

    if not txt_files:
        print("No .txt job descriptions found.")
        return

    provider = OpenAIProvider()

    for input_file in txt_files:
        output_file = OUTPUT_DIR / f"{input_file.stem}.json"

        if output_file.exists():
            print(f"Skipping already processed file: {input_file.name}")
            continue

        print(f"Analyzing: {input_file.name}")

        try:
            extracted_data = analyze_job(input_file, provider=provider)
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
