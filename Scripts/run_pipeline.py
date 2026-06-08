import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "Scripts"

PYTHON = sys.executable


def run_script(script_name):
    script_path = SCRIPTS_DIR / script_name

    print(f"\nRunning {script_name}...")

    result = subprocess.run(
        [PYTHON, str(script_path)],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    print(result.stdout)

    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"{script_name} failed.")


def main():
    run_script("analyze_job.py")
    run_script("import_json_to_db.py")
    run_script("analyze_database.py")

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()