# AI Career Assistant

An AI-powered career assistant designed to analyze job descriptions, extract skill requirements, track job applications, and generate career development insights using OpenAI through Sign in with ChatGPT.

## Project Objectives

- Use OpenAI's hosted model through the user's ChatGPT sign-in.
- Analyze job descriptions for technical skills, soft skills, tools, platforms, and certifications.
- Convert job description content into structured data for future storage and analysis.
- Track job applications, including applied roles, status updates, and outcomes.
- Identify repeated skill demands across targeted IT job descriptions.
- Generate insights to support career planning and skill prioritization.

## Current Technology Stack

- OpenAI Responses API
- OpenAI Structured Outputs
- Streamlit
- SQLite
- Windows 11

## Dashboard Workflows

- Review AI extraction before saving an application.
- Browse saved applications in one list, with each analyzed job available from its application.
- Track application stages, follow-ups, contacts, resume versions, and cover letters.
- Open each saved application in one profile to update its details, documents, and outcomes; the list and job workspace lead to the same editor.
- Inspect saved job descriptions with related skills and certifications.
- Compare resume profiles with the skills requested across saved jobs.
- Upload and remove category CVs for IT Support, Networking, Systems Administration, and other roles. Each job uses a matching CV for fit checks when available; removing a base CV keeps its saved job drafts.
- CV uploads retain the original PDF or DOCX for a formatted preview. DOCX previews use Microsoft Word on Windows. CVs uploaded before this feature need their original file attached once from the View dialog.
- Choose a starting CV in Tailoring Studio, review a job-specific draft, save it separately, and download an editable DOCX from Tailoring Studio or the job workspace.
- Export the filtered opportunities list as CSV.
- View status pipeline, application trends, follow-up history, and skill demand.

## Project Status

The application uses Sign in with ChatGPT for eligible structured job-description extraction requests. Local OAuth credentials are stored outside the project directory and are never committed.

## Setup

1. Install dependencies with `pip install -r requirements.txt`.
2. Optionally set `OPENAI_MODEL` in a local `.env` file; the default is `gpt-6.1-sol`.
3. Run `python Scripts/sign_in_with_chatgpt.py` once and approve ChatGPT plan usage in the browser.
4. Run the app with `python -m streamlit run App/dashboard.py`.

The sign-in flow uses a browser-based OAuth callback and stores its refresh token outside the project. It does not require an OpenAI API key or API credits; availability depends on the ChatGPT account's plan-sharing eligibility.

The supported app entry point is `App/dashboard.py`; see [architecture](docs/architecture.md) for the current modules and data flow.
