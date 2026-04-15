# AI IT Support Agent

This project is an end-to-end AI IT support automation system. It accepts natural language support requests, uses Groq (llama-3.3-70b-versatile) to plan actions, and executes them by navigating a mock Flask admin panel through Playwright like a human operator. It includes authentication, user management workflows, activity logging, and a CLI chat loop.

## Setup

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Playwright browser:

```bash
playwright install chromium
```

4. Set Groq API key in `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Run

```bash
python main.py
```

The app starts Flask on port 5050, launches Chromium in visible mode, logs in as admin, and waits for IT requests.

## Example Tasks

1. `reset password for john@company.com`
2. `create user Alice Cooper with email alice.cooper@company.com and role admin`
3. `disable user bob@company.com`
4. `check if user john@company.com exists, if not create them, then reset their password`
5. `disable all viewer role users`

## Architecture

```text
+---------------------------+
| CLI (main.py)             |
| - interactive chat loop   |
+------------+--------------+
             |
             v
+---------------------------+
| Task Router               |
| (agent/task_router.py)    |
| - complex decomposition   |
| - conditional branching   |
+------------+--------------+
             |
             v
+---------------------------+
| Browser Agent             |
| (agent/browser_agent.py)  |
| - Groq planning           |
| - Playwright execution    |
+-------+-------------------+
        |
        v
+---------------------------+
| Flask Admin Panel         |
| (admin_panel/app.py)      |
| - login/session auth      |
| - users CRUD-like actions |
| - SQLite + activity log   |
+---------------------------+
```

## Known Limitations

1. LLM-generated plans can vary and may occasionally require retries for ambiguous phrasing.
2. The automation relies on current UI text labels; major label changes can break selectors.
3. There is no pagination/filtering in the mock user table for very large user volumes.
4. The demo stores generated reset passwords in SQLite for simplicity and is not production security design.
5. Login credentials are hardcoded for the mock environment (`admin` / `admin123`).
