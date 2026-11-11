"""Fetch and lightly clean public job-posting pages before AI extraction."""

from __future__ import annotations

import html
import ipaddress
import json
import re
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class JobPageFetchError(RuntimeError):
    """Raised when a job URL cannot be converted into useful posting text."""


_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}
_DESCRIPTION_MARKERS = (
    "show-more-less-html__markup",
    "description__text",
    "jobs-description-content__text",
    "jobs-box__html-content",
    "job-description",
)
_JOB_CONTENT_SIGNALS = (
    "about the role",
    "about the job",
    "responsibilities",
    "requirements",
    "qualifications",
    "what you will do",
    "what you'll do",
    "skills and experience",
    "experience with",
    "key duties",
    "we are looking",
    "your responsibilities",
    "support",
)


class _JobPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.json_ld_parts: list[str] = []
        self.description_parts: list[str] = []
        self._description_depth = 0
        self._skip_stack: list[str] = []
        self._title_depth = 0
        self._json_ld_depth = 0
        self._active_json_ld: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = {str(key).lower(): str(value or "") for key, value in attrs}
        tag = tag.lower()
        marker = " ".join((attributes.get("class", ""), attributes.get("id", ""))).lower()
        if self._description_depth:
            self._description_depth += 1
        elif any(value in marker for value in _DESCRIPTION_MARKERS):
            self._description_depth = 1

        if tag == "meta":
            key = attributes.get("name") or attributes.get("property") or attributes.get("itemprop")
            value = attributes.get("content", "").strip()
            if key and value:
                self.meta[key.lower()] = value

        if tag == "title":
            self._title_depth += 1

        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._json_ld_depth += 1
            self._active_json_ld = []

        if tag in _SKIP_TAGS:
            self._skip_stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._description_depth:
            self._description_depth -= 1

        if tag == "title" and self._title_depth:
            self._title_depth -= 1

        if tag == "script" and self._json_ld_depth:
            payload = "".join(self._active_json_ld).strip()
            if payload:
                self.json_ld_parts.append(payload)
            self._active_json_ld = []
            self._json_ld_depth -= 1

        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data):
        if self._json_ld_depth:
            self._active_json_ld.append(data)

        if self._skip_stack:
            return

        value = data.strip()
        if not value:
            return

        if self._description_depth:
            self.description_parts.append(value)

        if self._title_depth:
            self.title_parts.append(value)
        else:
            self.text_parts.append(value)


def _clean_lines(values: list[str]) -> str:
    cleaned: list[str] = []
    previous = ""
    for value in values:
        value = re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()
        if not value or value == previous:
            continue
        cleaned.append(value)
        previous = value
    return "\n".join(cleaned)


def _find_job_posting(value):
    if isinstance(value, list):
        for item in value:
            result = _find_job_posting(item)
            if result:
                return result
        return None

    if not isinstance(value, dict):
        return None

    job_type = value.get("@type", "")
    if isinstance(job_type, list):
        is_job_posting = "JobPosting" in job_type
    else:
        is_job_posting = str(job_type).lower() == "jobposting"
    if is_job_posting:
        return value

    for child in value.values():
        result = _find_job_posting(child)
        if result:
            return result
    return None


def _structured_job_metadata(json_ld_parts: list[str]) -> dict[str, str]:
    for raw_json in json_ld_parts:
        try:
            payload = json.loads(raw_json)
        except (TypeError, json.JSONDecodeError):
            continue

        posting = _find_job_posting(payload)
        if not posting:
            continue

        organization = posting.get("hiringOrganization") or {}
        if isinstance(organization, list):
            organization = organization[0] if organization else {}
        location = posting.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        if isinstance(location, dict):
            address = location.get("address") or {}
            if isinstance(address, dict):
                location_text = ", ".join(
                    str(address.get(key, "")).strip()
                    for key in ("addressLocality", "addressRegion", "addressCountry")
                    if str(address.get(key, "")).strip()
                )
            else:
                location_text = str(address).strip()
        else:
            location_text = str(location).strip()

        return {
            "title": str(posting.get("title", "")).strip(),
            "company": str(organization.get("name", "") if isinstance(organization, dict) else organization).strip(),
            "location": location_text,
            "date_posted": str(posting.get("datePosted", "")).strip(),
            "employment_type": str(posting.get("employmentType", "")).strip(),
            "description": re.sub(r"\s+", " ", html.unescape(str(posting.get("description", "")))).strip(),
        }
    return {}


def _clean_structured_description(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", value).strip()


def _has_meaningful_job_content(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    word_count = len(re.findall(r"\b[\w'-]+\b", text))
    signal_count = sum(signal in text for signal in _JOB_CONTENT_SIGNALS)
    return word_count >= 45 and signal_count >= 1


def _validate_public_url(url: str) -> str:
    value = str(url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise JobPageFetchError("Enter a complete public URL beginning with http:// or https://.")
    if parsed.username or parsed.password:
        raise JobPageFetchError("URLs containing embedded usernames or passwords are not supported.")

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname in {"localhost", "localhost.localdomain"}:
        raise JobPageFetchError("Localhost URLs are not valid job-posting URLs.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
        raise JobPageFetchError("Private or local network URLs are not supported.")
    return value


def source_label_for_url(url: str) -> str:
    hostname = (urlparse(url).hostname or "").lower()
    if "linkedin" in hostname:
        return "LinkedIn"
    if "seek" in hostname:
        return "Seek"
    if "indeed" in hostname:
        return "Indeed"
    if "jora" in hostname:
        return "Jora"
    if "workday" in hostname:
        return "Workday"
    if "smartrecruiters" in hostname:
        return "SmartRecruiters"
    if "greenhouse" in hostname:
        return "Greenhouse"
    if "lever" in hostname:
        return "Lever"
    return hostname.removeprefix("www.") or "Job website"


def _read_html_page(url: str, timeout: int) -> tuple[str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "AI-Career-Assistant/1.0 (public job posting reader)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise JobPageFetchError("This URL did not return an HTML job posting.")
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read(4_000_000).decode(charset, errors="replace")
        return body, response.geturl() or url


def _read_with_rate_limit_retry(url: str, timeout: int) -> tuple[str, str]:
    try:
        return _read_html_page(url, timeout)
    except HTTPError as error:
        if error.code != 429:
            raise
        time.sleep(1)
        return _read_html_page(url, timeout)


def _parse_job_page(body: str, *, linkedin: bool = False) -> tuple[_JobPageParser, dict[str, str], str]:
    parser = _JobPageParser()
    try:
        parser.feed(body)
        parser.close()
    except Exception as error:
        raise JobPageFetchError("The page could not be read as an HTML job posting.") from error

    metadata = _structured_job_metadata(parser.json_ld_parts)
    metadata["description"] = _clean_structured_description(metadata.get("description", ""))
    page_text = _clean_lines(parser.text_parts)
    structured = metadata.get("description", "")
    scoped = _clean_lines(parser.description_parts)
    if linkedin:
        page_text = structured if _has_meaningful_job_content(structured) else scoped
    elif _has_meaningful_job_content(structured):
        page_text = structured
    elif _has_meaningful_job_content(scoped):
        page_text = scoped
    return parser, metadata, page_text


def _linkedin_guest_url(url: str) -> str:
    if "linkedin.com" not in (urlparse(url).hostname or "").lower():
        return ""
    match = re.search(r"/jobs/view/(\d+)", urlparse(url).path)
    if not match:
        return ""
    return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{match.group(1)}"


def fetch_job_posting(url: str, timeout: int = 15) -> dict[str, str]:
    """Fetch a public job page and return cleaned text plus extraction hints."""

    validated_url = _validate_public_url(url)
    guest_url = _linkedin_guest_url(validated_url)
    is_linkedin = bool(guest_url)
    try:
        body, final_url = _read_with_rate_limit_retry(validated_url, timeout)
        parser, metadata, page_text = _parse_job_page(body, linkedin=is_linkedin)
    except JobPageFetchError:
        raise
    except HTTPError as error:
        if error.code != 429 or not guest_url:
            raise JobPageFetchError(
                f"The job site returned HTTP {error.code}. It may require login or block automated access."
            ) from error
        try:
            body, _ = _read_html_page(guest_url, timeout)
            parser, metadata, page_text = _parse_job_page(body, linkedin=True)
            if not _has_meaningful_job_content(page_text):
                raise JobPageFetchError("The public posting did not include its job description.")
            final_url = validated_url
        except (JobPageFetchError, HTTPError, URLError, TimeoutError, OSError) as guest_error:
            raise JobPageFetchError(
                "LinkedIn temporarily limited access to this posting. Try again shortly or paste the job description."
            ) from guest_error
    except (URLError, TimeoutError, OSError) as error:
        raise JobPageFetchError(
            "The job page could not be reached. Check the URL or use the paste fallback."
        ) from error

    if not _has_meaningful_job_content(page_text):
        if guest_url:
            try:
                guest_body, _ = _read_html_page(guest_url, timeout)
                guest_parser, guest_metadata, guest_page_text = _parse_job_page(guest_body, linkedin=True)
                if _has_meaningful_job_content(guest_page_text):
                    parser = guest_parser
                    metadata.update({key: value for key, value in guest_metadata.items() if value})
                    page_text = guest_page_text
                    final_url = validated_url
            except (JobPageFetchError, HTTPError, URLError, TimeoutError, OSError):
                pass

    if not _has_meaningful_job_content(page_text):
        raise JobPageFetchError(
            "The site exposed job metadata but not the readable job-description body. "
            "It may require login or dynamic rendering; use the paste fallback."
        )

    metadata_lines = [
        f"Source URL: {final_url}",
        f"Structured title: {metadata.get('title', '')}",
        f"Structured company: {metadata.get('company', '')}",
        f"Structured location: {metadata.get('location', '')}",
        f"Date posted: {metadata.get('date_posted', '')}",
        f"Employment type: {metadata.get('employment_type', '')}",
    ]
    return {
        "url": final_url,
        "source_label": source_label_for_url(final_url),
        "title_hint": metadata.get("title", "") or parser.meta.get("og:title", "") or _clean_lines(parser.title_parts),
        "company_hint": metadata.get("company", ""),
        "text": "\n".join(line for line in metadata_lines if line.split(": ", 1)[-1]) + "\n\n" + page_text,
    }
