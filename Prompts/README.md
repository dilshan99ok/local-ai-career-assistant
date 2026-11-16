# AI guidance library

These Markdown files contain the fixed instructions sent to the AI. `Scripts/prompt_loader.py` reads them when a request is built. Job descriptions, CV text, application details, and saved screening results are inserted at runtime; do not put personal data or credentials in this directory.

| Workflow | Task prompt | Response instructions |
| --- | --- | --- |
| Job extraction | `job-extraction-prompt.md` | `job-extraction-system.md` |
| Job checklist | `job-checklist.md` | `json-output-system.md` |
| CV evidence review | `cv-evidence-review.md` | `cv-evidence-system.md` |
| Resume change plan | `resume-suggestions.md` | `resume-editor-system.md` |
| Tailored resume draft | `resume-draft.md` | `resume-editor-system.md` |
| Cover letter | `cover-letter.md` | `cover-letter-system.md` |
| Follow-up email | `follow-up-email.md` | `follow-up-system.md` |

`resume-screening-review.md` supplies the saved checklist and CV evidence to either resume-writing task when a complete review exists. `default-output-system.md` is the provider fallback for text requests without workflow-specific response instructions.

`cv-duration-merge.md` reconciles duration requirements after individual CV sections have been reviewed. It counts overlapping experience periods only once and leaves unclear dates unresolved.

Edit the wording in the relevant file and commit it with any related code or tests. Placeholders use `{{UPPERCASE_NAME}}`; keep the names in sync with the `render_prompt(...)` call. Pasted job and CV text is substituted once, so placeholder-looking text inside a source document stays source text. Run `python -m unittest discover -s Tests -p 'test_*.py' -q` after editing.

Prompt content is part of the relevant extraction and screening cache keys. New AI calls use updated wording. A saved checklist records the guidance hash it was created with; older checklists are labelled in Fit & gaps and can be regenerated there. Changing CV review guidance invalidates its saved result; use **Reanalyze CV pool**. Existing checklist criteria can also be corrected in Fit & gaps. Job extraction fields and types are constrained by `JOB_EXTRACTION_SCHEMA` in `Scripts/ai_provider.py`; changing that structure requires a code change as well as prompt wording.
