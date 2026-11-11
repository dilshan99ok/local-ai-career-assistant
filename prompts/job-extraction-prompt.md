# Job Description Extraction Prompt

Analyze the job description below and return ONLY valid JSON using this structure:

{
  "company": "",
  "recruiter_name": "",
  "parent_company": "",
  "end_client_name": "",
  "end_client_industry": "",
  "posting_type": "",
  "job_title": "",
  "domain": "",
  "location": "",
  "salary_range": "",
  "work_mode": "Not specified",
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
- Preserve the complete advertised job title, including Junior, Senior, Graduate, Associate, Lead, Principal, Staff, or numeric level markers.
- Never shorten a job title by removing its seniority or level prefix.
- For a recruiter or talent consultancy posting, set company to the named recruiter when the end client is unnamed.
- recruiter_name is the named recruitment agency or talent consultancy, if one is identified.
- parent_company is the named parent company or division owner, if one is identified.
- end_client_name is the hiring organization only when its name is explicitly stated; never invent it.
- end_client_industry may identify an unnamed client by industry, such as Telecommunications.
- posting_type should be Recruiter / consultancy, Direct employer, or an empty string when unclear.
- location should contain the explicitly stated job location or locations.
- salary_range should contain the explicitly stated salary or remuneration range.
- work_mode must be Not specified, On-site, Hybrid, or Remote, based only on explicit wording.
- If the company is not clearly stated, return an empty company value.
- The domain should be one of the closest matching areas, such as:
  - IT Support
  - Networking
  - Cloud
  - Cybersecurity
  - Systems Administration
  - Data Centre
  - Infrastructure
  - Other
- Technical skills are general technical abilities.
- Soft skills are communication, teamwork, customer service, problem-solving, leadership, and similar qualities.
- Tools/platforms are named systems, applications, operating systems, cloud platforms, or ticketing tools.
- Certifications are formal qualifications or certifications mentioned in the job description.
- Domain-specific skills are specialized skills related to the identified domain.
- Responsibilities are duties or tasks the role requires.
- Company should contain the primary named organisation associated with the posting.
- When a recruiter is advertising on behalf of an undisclosed client, company should be the recruiter so the saved application has a usable organization name.
- Technical skills should contain general technical competencies and troubleshooting abilities.
- Tools/platforms should contain named products, systems, software, operating systems, cloud platforms, ticketing tools, or vendor technologies.
- Certifications should include every explicitly mentioned certification, qualification, certificate, or accreditation.
- Domain-specific skills should use concise labels strongly linked to the selected domain.
- Keep responsibilities as short action-based statements.
- Avoid duplicate items across fields.
- Do not infer skills that are not clearly stated or strongly implied.
- Do not include benefits, culture statements, or generic equal-opportunity text. Keep explicit salary information only in salary_range.

Job description:
[PASTE JOB DESCRIPTION HERE]
