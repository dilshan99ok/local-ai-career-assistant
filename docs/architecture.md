# Architecture

## Main workflow

1. The user submits a public job URL or pastes a job description in the Streamlit dashboard.
2. `Scripts/job_url.py` reads public HTML when a URL is supplied. The user can paste the description if the site blocks access.
3. `Scripts/ai_helper.py` sends the description through `Scripts/ai_provider.py` and validates the extracted fields. The review screen allows corrections before saving.
4. `App/app_utils/database.py` stores the job, application, extracted skills, status history, and follow-up details in SQLite.
5. The Applications workspace lists tracked applications. Each row opens its job workspace or application profile. Job analysis and skill demand use jobs linked to a saved application.

## Components

| Area | Primary files | Responsibility |
| --- | --- | --- |
| Dashboard and navigation | `App/dashboard.py`, `App/app_utils/navigation.py` | Sidebar pages, contextual job workspaces, back navigation |
| Applications | `App/app_pages/applications_page.py`, `App/app_pages/opportunities_page.py` | URL or pasted-description intake, application list, pipeline, tracking, and application profile |
| Job details and skills | `App/app_pages/job_detail_page.py`, `App/app_pages/skills_page.py` | Per-job details and demand analysis |
| Resumes and tailoring | `App/app_pages/resume_page.py`, `App/app_pages/tailoring_page.py` | Source CVs, local fit and gaps, resume and cover-letter drafts |
| AI and authentication | `Scripts/ai_provider.py`, `Scripts/ai_helper.py`, `Scripts/chatgpt_auth.py` | ChatGPT sign-in, extraction, and generation |
| Storage | `App/app_utils/database.py` | SQLite schema, migrations, queries, and updates |
| Local analysis | `Scripts/job_fit.py`, `Scripts/skill_analysis.py`, `Scripts/skill_taxonomy.py` | Repeatable fit and skill summaries |

## Data and files

The SQLite database is under `Data/database/` and is excluded from Git. It contains saved jobs, applications, skill and certification data, resume profiles, document drafts, and tracking history. Uploaded CVs retain extracted text and, for new uploads, the original file so the app can preview its layout. DOCX preview uses Microsoft Word on Windows to render a temporary PDF. Files uploaded before original-file storage was added can be attached from the CV preview.

ChatGPT OAuth credentials are stored outside the repository. `.env` files, the database, raw job descriptions, and processed exports are ignored by Git. The repository contains code and configuration examples only.

## Supported entry points

- Start the dashboard: `python -m streamlit run App/dashboard.py`
- Sign in for AI features: `python Scripts/sign_in_with_chatgpt.py`
- Create or update the database schema: `python Scripts/create_database.py`
- Run the tests: `python -m unittest discover -s Tests -p 'test_*.py' -q`

The first version's one-off database, report, and batch-pipeline scripts have been removed. `Scripts/create_database.py` remains the supported schema setup command.
