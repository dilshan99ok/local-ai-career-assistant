"""Compatibility entry points for the CV pool screening workflow."""

from Scripts.ats_review import (
    SCHEMA as REVIEW_SCHEMA_VERSION,
    build_edits,
    evidence_score,
    extraction_issues,
    fingerprint as recommendation_fingerprint,
    generate_checklist as generate_job_checklist,
    parse_assessments,
    rank_reviews,
    review_pool as generate_resume_recommendation,
    source_hash,
    split_sections as split_review_sections,
    validate_checklist,
)
