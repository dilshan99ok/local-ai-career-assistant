# System Architecture

## Overview

The Local AI Career Assistant is designed as a self-hosted career intelligence system that uses local open-weight language models to analyze job descriptions, extract structured skill data, track applications, and generate career development insights.

The system is designed around a modular architecture so that each component can be improved or replaced over time.

## Architecture Layers

### 1. Input Layer

The input layer contains the raw information that will be analyzed or tracked by the system.

- Job descriptions
- Resume/CV content
- Application records
- User notes

### 2. AI Layer

The AI layer is responsible for understanding and extracting useful information from unstructured text.

Current components:

- Ollama
- Qwen 2.5 7B
- Open-weight local language model execution

Purpose:

- Analyze job descriptions
- Extract technical skills, soft skills, tools, platforms, and certifications
- Convert unstructured text into structured JSON
- Support career-related question answering

### 3. User Interface Layer

The user interface layer provides a practical way to interact with the local AI model.

Current component:

- Open WebUI

Purpose:

- Chat with the local AI model
- Test job description analysis prompts
- Validate structured JSON extraction
- Experiment with career assistant workflows

### 4. Processing Layer

The processing layer will automate the extraction workflow.

Planned component:

- Python extraction pipeline

Purpose:

- Read job description files
- Send job descriptions to the local AI model through Ollama
- Receive structured JSON output
- Validate and clean extracted data
- Prepare data for database storage

### 5. Storage Layer

The storage layer will store extracted job intelligence data and application tracking information.

Planned component:

- SQLite database

Planned datasets:

#### Job Intelligence Data

- Role titles
- Role categories
- Technical skills
- Soft skills
- Tools and platforms
- Certifications
- Networking concepts
- Security concepts
- Experience levels

#### Application Tracking Data

- Company
- Job title
- Location
- Work mode
- Application status
- Date applied
- Interview status
- Outcome notes

### 6. Analytics Layer

The analytics layer will generate insights from the stored data.

Planned analytics:

- Most requested technical skills
- Most requested soft skills
- Common tools and platforms
- Certification demand trends
- Networking and security skill trends
- Role category comparisons
- Application status summaries
- Skill gap insights

## High-Level Workflow

```text
Job Description
        ↓
AI Extraction Engine
        ↓
Structured JSON Output
        ↓
SQLite Database
        ↓
Analytics Engine
        ↓
Career Insights
