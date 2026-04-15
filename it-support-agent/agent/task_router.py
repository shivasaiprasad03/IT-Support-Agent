import json
import re

from agent.llm_client import ask_groq


def _extract_email(task: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+", task)
    return match.group(0).lower() if match else ""


def _extract_role(task: str) -> str:
    match = re.search(r"role\s+(user|admin|viewer)", task.lower())
    return match.group(1) if match else "user"


def _decompose_subtasks(task: str) -> list[str]:
    system_prompt = (
        "You break IT support requests into concise executable sub-tasks. "
        "Return ONLY JSON array of strings. No markdown."
    )
    user_prompt = (
        f"Task: {task}\n"
        "Split into ordered sub-tasks that can each be executed independently in browser UI."
    )
    raw = ask_groq(system_prompt, user_prompt)

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if isinstance(item, str) and item.strip()]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return [str(item) for item in parsed if isinstance(item, str) and item.strip()]
        except json.JSONDecodeError:
            pass

    # Fallback split for robustness when model output is malformed.
    return [part.strip() for part in re.split(r"\bthen\b", task, flags=re.IGNORECASE) if part.strip()]


def handle_task(task: str, agent) -> str:
    lowered = task.lower().strip()

    if "check if user" in lowered and "exists" in lowered:
        email = _extract_email(task)
        if not email:
            return "Could not identify an email in the task."

        agent.page.goto(f"{agent.base_url}/users")
        page_text = agent.page_text().lower()

        if email in page_text:
            summaries = [f"User {email} already exists."]
            if "reset" in lowered and "password" in lowered:
                summaries.append(agent.execute_task(f"reset password for {email}"))
            return " ".join(summaries)

        role = _extract_role(task)
        guessed_name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        create_summary = agent.execute_task(
            f"create user {guessed_name} with email {email} and role {role}"
        )

        summaries = [f"User {email} did not exist, so it was created.", create_summary]
        if "reset" in lowered and "password" in lowered:
            summaries.append(agent.execute_task(f"reset password for {email}"))

        return " ".join(summaries)

    if "disable all viewer role users" in lowered or "disable all viewers" in lowered:
        agent.page.goto(f"{agent.base_url}/users")
        rows = agent.page.locator("tbody tr")
        row_count = rows.count()
        disabled_emails: list[str] = []

        for index in range(row_count):
            row = rows.nth(index)
            row_text = row.inner_text()
            row_lower = row_text.lower()
            if "viewer" in row_lower and "active" in row_lower:
                email_match = re.search(r"[\w.+-]+@[\w.-]+", row_text)
                if email_match:
                    email = email_match.group(0).lower()
                    agent.execute_task(f"disable user {email}")
                    disabled_emails.append(email)

        if not disabled_emails:
            return "No active viewer users found to disable."

        return f"Disabled {len(disabled_emails)} viewer user(s): {', '.join(disabled_emails)}"

    if " then " in lowered:
        subtasks = _decompose_subtasks(task)
        summaries = []
        for subtask in subtasks:
            summaries.append(agent.execute_task(subtask))
        return " ".join(summaries)

    return agent.execute_task(task)
