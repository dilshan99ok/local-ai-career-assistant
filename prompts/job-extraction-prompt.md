# Job Description Extraction Prompt

Analyze the job description below and return ONLY valid JSON using this structure:

{
  "job_title": "",
  "domain": "",
  "technical_skills": [],
  "soft_skills": [],
  "tools_platforms": [],
  "certifications": [],
  "domain_specific_skills": [],
  "responsibilities": []
}

Rules:
- Return JSON only.
- Do not include explanations before or after the JSON.
- Keep values concise.
- Use the exact field names shown above.
- If a field is not mentioned, return an empty array or empty string.
- The domain should be one of the closest matching areas, such as:
  - IT Support
  - Networking
  - Cloud
  - Cybersecurity
  - Systems Administration
  - Data Centre
  - Software Development
  - Other
- Technical skills are general technical abilities.
- Soft skills are communication, teamwork, customer service, problem-solving, leadership, and similar qualities.
- Tools/platforms are named systems, applications, operating systems, cloud platforms, or ticketing tools.
- Certifications are formal qualifications or certifications mentioned in the job description.
- Domain-specific skills are specialized skills related to the identified domain.
- Responsibilities are duties or tasks the role requires.

Job description:
[PASTE JOB DESCRIPTION HERE]
