"""Resume file extraction and lightweight detail detection.

The upload step stays reviewable: it extracts readable text from a file, detects
obvious details locally, and lets the user edit everything before saving. No
resume content is sent to OpenAI by this module.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class ResumeImportError(ValueError):
    """Raised when a resume file cannot be converted into readable text."""


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_docx_text(data: bytes) -> str:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            document_xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(document_xml)
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        raise ResumeImportError("The DOCX file could not be read.") from error

    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text.strip())
    return "\n".join(paragraphs)


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ResumeImportError(
            "PDF support is not installed. Run `pip install -r requirements.txt`."
        ) from error

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as error:  # pypdf exposes several parser-specific exceptions.
        raise ResumeImportError("The PDF file could not be read.") from error
    return "\n\n".join(page for page in pages if page)


def extract_resume_text(file_name: str, data: bytes) -> str:
    """Extract plain text from a supported resume file."""

    suffix = Path(file_name or "").suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        text = _decode_text(data)
    elif suffix == ".docx":
        text = _extract_docx_text(data)
    elif suffix == ".pdf":
        text = _extract_pdf_text(data)
    else:
        raise ResumeImportError(
            "Unsupported resume format. Use PDF, DOCX, TXT, or Markdown."
        )

    normalized = re.sub(r"\r\n?", "\n", text or "")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


SECTION_ALIASES = {
    "summary": {"summary", "professional summary", "profile", "about me", "objective"},
    "experience": {"experience", "work experience", "professional experience", "employment history"},
    "education": {"education", "academic background", "qualifications"},
    "certifications": {"certifications", "certificates", "licenses & certifications", "licences & certifications"},
    "projects": {"projects", "selected projects", "personal projects"},
}


def _section_content(text: str) -> dict[str, str]:
    aliases = {alias: key for key, values in SECTION_ALIASES.items() for alias in values}
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        cleaned = line.strip().strip("#*- ").strip()
        heading = aliases.get(cleaned.lower())
        if heading:
            current = heading
            sections.setdefault(current, [])
        elif current and cleaned:
            sections[current].append(cleaned)
    return {key: "\n".join(value).strip() for key, value in sections.items() if value}


def extract_resume_details(text: str) -> dict:
    """Detect obvious resume details without inventing or calling an API."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidate_name = ""
    if lines:
        first_line = re.sub(r"^[#*\-]+\s*", "", lines[0]).strip()
        if (
            2 <= len(first_line.split()) <= 5
            and not re.search(r"@|https?://|\d", first_line)
            and first_line.lower() not in {"resume", "curriculum vitae", "cv"}
        ):
            candidate_name = first_line

    emails = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, flags=re.I)
    phones = re.findall(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", text)
    links = re.findall(r"https?://[^\s)]+", text, flags=re.I)

    headline = ""
    if candidate_name:
        for line in lines[1:5]:
            if line.lower() not in {"resume", "curriculum vitae", "cv"} and not re.search(
                r"@|https?://|(?:\+?\d[\d ()-]{7,}\d)", line
            ):
                headline = line
                break

    return {
        "candidate_name": candidate_name,
        "headline": headline,
        "email": emails[0] if emails else "",
        "phone": phones[0].strip() if phones else "",
        "links": links[:5],
        "sections": _section_content(text),
    }
