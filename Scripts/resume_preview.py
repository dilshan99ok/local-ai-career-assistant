"""Render an uploaded DOCX with Microsoft Word for an accurate PDF preview."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


class ResumePreviewError(RuntimeError):
    pass


def docx_to_pdf(data: bytes) -> bytes:
    if os.name != "nt":
        raise ResumePreviewError("DOCX preview requires Microsoft Word on Windows.")

    script = Path(__file__).with_name("word_to_pdf.ps1")
    with tempfile.TemporaryDirectory(prefix="career-cv-preview-") as folder:
        source = Path(folder) / "resume.docx"
        output = Path(folder) / "resume.pdf"
        source.write_bytes(data)
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-InputPath", str(source), "-OutputPath", str(output)],
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ResumePreviewError("Word could not render this DOCX preview.") from error
        if result.returncode != 0 or not output.exists():
            raise ResumePreviewError("Word could not render this DOCX preview.")
        return output.read_bytes()
