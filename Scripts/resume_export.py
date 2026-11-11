"""Create an editable Word document from a reviewed tailored resume draft."""

from __future__ import annotations

import io
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", WORD_NS)


def safe_resume_filename(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "resume")).strip("._-")
    return (stem[:80] or "resume") + ".docx"


def _plain_text(value: str) -> str:
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    return re.sub(r"[*_`]+", "", value).strip()


def build_resume_docx(content: str) -> bytes:
    """Export reviewed text as a simple, editable DOCX without changing its facts."""
    if not str(content or "").strip():
        raise ValueError("The tailored resume is empty.")

    document = ET.Element(f"{{{WORD_NS}}}document")
    body = ET.SubElement(document, f"{{{WORD_NS}}}body")
    for line in str(content).splitlines():
        line = line.strip()
        if not line:
            continue
        heading = line.startswith("#")
        bullet = bool(re.match(r"^[-*]\s+", line))
        if heading:
            line = line.lstrip("# ")
        elif bullet:
            line = "• " + re.sub(r"^[-*]\s+", "", line)
        text = _plain_text(line)
        if not text:
            continue
        paragraph = ET.SubElement(body, f"{{{WORD_NS}}}p")
        run = ET.SubElement(paragraph, f"{{{WORD_NS}}}r")
        if heading:
            properties = ET.SubElement(run, f"{{{WORD_NS}}}rPr")
            ET.SubElement(properties, f"{{{WORD_NS}}}b")
            ET.SubElement(properties, f"{{{WORD_NS}}}sz", {f"{{{WORD_NS}}}val": "28"})
        text_node = ET.SubElement(run, f"{{{WORD_NS}}}t")
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text_node.text = text
    ET.SubElement(body, f"{{{WORD_NS}}}sectPr")

    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '</Relationships>'
    )
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", ET.tostring(document, encoding="utf-8", xml_declaration=True))
    return output.getvalue()
