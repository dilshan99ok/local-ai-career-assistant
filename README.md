# Local AI Career Assistant

A self-hosted AI-powered career intelligence system that analyzes job descriptions, extracts structured skill data, tracks job applications, and helps identify follow-up actions.

## Overview

This project combines local open-weight AI models with Python and SQLite to support job search organization and career planning.

The system uses a local AI model to convert unstructured job descriptions into structured JSON data, then stores the extracted information in a SQLite database for analysis and application tracking.

## Key Features

- Local AI-powered job description analysis
- Structured JSON extraction from job descriptions
- Batch processing of multiple job descriptions
- SQLite database storage
- Skill, tool, certification, and domain analytics
- Application tracking
- Follow-up date tracking for applied jobs
- Simple command-line pipeline runner

## Technology Stack

- Python
- SQLite
- Ollama
- Qwen 2.5 7B
- Open WebUI
- Docker Desktop

## Current Workflow

```text
Job Description (.txt)
        ↓
Ollama + Qwen 2.5
        ↓
Structured JSON
        ↓
SQLite Database
        ↓
Analytics Report
