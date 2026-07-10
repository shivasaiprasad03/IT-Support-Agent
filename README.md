# IT-Support-Agent

An end-to-end **AI-powered IT support automation demo** built with Python, Flask, Playwright, and Groq.

This project accepts natural language IT requests, uses an LLM to plan actions, and executes those actions against a mock admin web panel.

## Overview

`IT-Support-Agent` combines:

- A **Flask-based admin panel** (mock IT system)
- A **browser automation agent** using Playwright
- An **LLM planning layer** (Groq `llama-3.3-70b-versatile`)
- A **task router** that handles decomposition and conditional workflows
- A **CLI interface** for interactive support requests

## Repository Structure

```text
.
├── .gitignore
└── it-support-agent/
    ├── README.md
    ├── requirements.txt
    ├── main.py
    ├── admin_panel/
    └── agent/
```

## How It Works

1. `main.py` loads environment variables and starts the Flask app (`127.0.0.1:5050`) in a background thread.
2. A browser-based agent is initialized and navigates the admin panel.
3. You submit support requests in plain English from the CLI.
4. The task router and LLM generate execution steps.
5. Playwright performs actions in the UI (e.g., user checks, creation, password reset, disable operations).

## Tech Stack

- **Python 3**
- **Flask 3.0.3**
- **Playwright 1.52.0**
- **Groq SDK 0.26.0**
- **python-dotenv 1.0.1**
- **SQLite** (inside the mock admin panel)

## Prerequisites

- Python 3.10+
- pip
- Playwright browser binaries
- A valid Groq API key

## Setup

From the `it-support-agent/` directory:

```bash
pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Run

From `it-support-agent/`:

```bash
python main.py
```

You should see:

- Flask server start on `http://127.0.0.1:5050`
- Browser agent initialization
- CLI prompt: `IT Support Agent ready. Type your request...`

## Example Requests

- `reset password for john@company.com`
- `create user Alice Cooper with email alice.cooper@company.com and role admin`
- `disable user bob@company.com`
- `check if user john@company.com exists, if not create them, then reset their password`
- `disable all viewer role users`

## Architecture (High-Level)

```text
CLI (main.py)
   │
   ▼
Task Router (agent/task_router.py)
   │
   ▼
Browser Agent (agent/browser_agent.py)
   │
   ▼
Flask Admin Panel (admin_panel/app.py)
```

## Current Limitations

- LLM plans can vary for ambiguous prompts.
- Selector strategy depends on current UI labels/text.
- Mock panel scalability features (e.g., pagination) are limited.
- Reset-password handling in demo storage is simplified and not production security design.
- Demo credentials are hardcoded for the mock environment.

