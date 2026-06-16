Local AI Career Assistant
A personal project I built to help organise my own job search using a locally hosted AI model. It reads job descriptions, pulls out the useful details automatically, and keeps everything tracked in one place instead of scattered across spreadsheets and saved emails.
What it does
I built this because I was tired of manually copying job details into a spreadsheet every time I applied somewhere. Now I just paste the job description in, and the app handles the rest using a locally run AI model (Qwen 2.5, through Ollama). It pulls out the skills, certifications, and key requirements, and saves everything to a local database so I can search and filter through it later.
It also tracks my actual applications, including follow-up dates, so I have a clear picture of where things stand without having to remember everything myself.
Built with
Python, Streamlit, SQLite, Pandas, Altair, Ollama, and Qwen 2.5 (7B), running locally through Docker.
How it works
It's a fairly simple pipeline. I paste in a job description, it gets processed by the local AI model, the structured details get extracted and cleaned up, and everything lands in a SQLite database. From there, the Streamlit dashboard gives me a way to actually look at and use the data.
textJob Description
        ↓
Ollama + Qwen 2.5
        ↓
Structured JSON extraction
        ↓
Skill and certification fallback logic
        ↓
SQLite database
        ↓
Streamlit dashboard
The main pages
Dashboard — A quick overview of where my job search stands, including how many applications I've sent, what's pending follow-up, and which domains and skills keep showing up.
Applications — Where I add, edit, and track my actual applications. I can paste a job description straight in to create a new entry.
Skills Intelligence — Shows me the skills and certifications that keep coming up across the jobs I've looked at, which has been genuinely useful for figuring out what to focus on.
Jobs — All the analysed job descriptions I've saved, with search and filtering so I can go back and find specific ones.
Database
Everything is stored locally in SQLite, across a few tables: jobs, applications, job_items, job_skills, and job_certifications.
Why I built this
Mostly to make my own job search less chaotic, and partly because I wanted to get hands-on experience with local AI workflows, structured data extraction, and building a proper Streamlit dashboard from scratch.
Note
This is a personal project, built for my own use and to learn from. It's not meant to compete with or replace actual recruitment platforms or career tools.
