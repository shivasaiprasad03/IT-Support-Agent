import json
import os
import re
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from agent.llm_client import ask_groq


class BrowserAgent:
    def __init__(self, base_url: str = "http://localhost:5050") -> None:
        self.base_url = base_url.rstrip("/")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self._login()

    def _login(self) -> None:
        try:
            self.page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")
            self.page.get_by_label("Username").fill("admin")
            self.page.get_by_label("Password").fill("admin123")
            self.page.get_by_role("button", name="Log In").click()
            self.page.wait_for_load_state("domcontentloaded")

            if "/login" in self.page.url:
                raise RuntimeError("Login failed: still on login page after submitting credentials.")
        except Exception as exc:
            self.close()
            raise RuntimeError(f"Login failed: {exc}") from exc

    def close(self) -> None:
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.playwright.stop()
        except Exception:
            pass

    def execute_task(self, task: str) -> str:
        steps = self._plan_steps(task)
        if not steps:
            return f"No actionable steps were generated for: {task}"

        errors: list[str] = []
        executed = 0

        for index, step in enumerate(steps, start=1):
            action = str(step.get("action", "")).strip().lower()
            target = str(step.get("target", "")).strip()
            value = str(step.get("value", "")).strip()

            print(f"[Agent] Executing step {index}: {action} -> {target}")

            try:
                self._execute_step(action=action, target=target, value=value)
                executed += 1
            except Exception as exc:
                error_text = f"Step {index} failed ({action} -> {target}): {exc}"
                print(f"[Agent] {error_text}")
                errors.append(error_text)

        os.makedirs("screenshots", exist_ok=True)
        self.page.screenshot(path=os.path.join("screenshots", "last_action.png"), full_page=True)

        if errors:
            return (
                f"Completed {executed}/{len(steps)} steps for task '{task}'. "
                f"Encountered {len(errors)} error(s): {' | '.join(errors)}"
            )

        return f"Successfully completed all {executed} steps for task: {task}."

    def _plan_steps(self, task: str) -> list[dict[str, Any]]:
        deterministic_steps = self._plan_deterministic_steps(task)
        if deterministic_steps is not None:
            return deterministic_steps

        system_prompt = (
            "You are planning browser UI automation steps for a Flask IT admin panel. "
            "Return only a JSON array. Each item must be an object with keys: "
            "action, target, value.\n"
            "Allowed actions: goto, click, fill, select, wait.\n"
            "Panel routes: /login, /, /users, /users/new.\n"
            "Common controls: Username, Password, Log In, Create User, "
            "Reset Password for <email>, Disable User <email>, Enable User <email>, role dropdown.\n"
            "Do not include commentary or markdown."
        )
        user_prompt = f"Task: {task}\nReturn JSON array steps only."

        raw = ask_groq(system_prompt, user_prompt)
        return self._parse_json_steps(raw)

    def _plan_deterministic_steps(self, task: str) -> list[dict[str, Any]] | None:
        lowered = task.lower().strip()
        email_match = re.search(r"[\w.+-]+@[\w.-]+", task)
        email = email_match.group(0).lower() if email_match else ""

        if "reset" in lowered and "password" in lowered and email:
            password_match = re.search(
                r"(?:as|to)\s+(?P<password>[^,.;]+)$",
                task.strip(),
                flags=re.IGNORECASE,
            )
            new_password = password_match.group("password").strip() if password_match else ""

            return [
                {"action": "goto", "target": "/login", "value": ""},
                {"action": "fill", "target": "Username", "value": "admin"},
                {"action": "fill", "target": "Password", "value": "admin123"},
                {"action": "click", "target": "Log In", "value": ""},
                {"action": "goto", "target": "/users", "value": ""},
                {"action": "click", "target": f"Reset Password for {email}", "value": ""},
                {"action": "fill", "target": "Password", "value": new_password},
                {"action": "fill", "target": "Confirm Password", "value": new_password},
                {"action": "click", "target": "Reset Password", "value": ""},
            ]

        create_match = re.search(
            r"create(?:\s+a)?(?:\s+new)?\s+user\s+(?P<name>.+?)\s+with\s+email\s+(?P<email>[\w.+-]+@[\w.-]+)(?:\s+and\s+role\s+(?P<role>user|admin|viewer))?",
            task,
            flags=re.IGNORECASE,
        )
        if create_match:
            full_name = create_match.group("name").strip()
            email = create_match.group("email").strip().lower()
            role = (create_match.group("role") or "user").strip().lower()

            return [
                {"action": "goto", "target": "/login", "value": ""},
                {"action": "fill", "target": "Username", "value": "admin"},
                {"action": "fill", "target": "Password", "value": "admin123"},
                {"action": "click", "target": "Log In", "value": ""},
                {"action": "goto", "target": "/users/new", "value": ""},
                {"action": "fill", "target": "Full Name", "value": full_name},
                {"action": "fill", "target": "Email", "value": email},
                {"action": "select", "target": "Role", "value": role},
                {"action": "click", "target": "Create User", "value": ""},
            ]

        return None

    def _parse_json_steps(self, text: str) -> list[dict[str, Any]]:
        cleaned = text.strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [step for step in parsed if isinstance(step, dict)]
        except json.JSONDecodeError:
            pass

        match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
        if not match:
            return []

        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, list):
                return [step for step in parsed if isinstance(step, dict)]
        except json.JSONDecodeError:
            return []

        return []

    def _resolve_url(self, target: str) -> str:
        if target.startswith("http://") or target.startswith("https://"):
            return target

        route_match = re.search(r"/[-a-zA-Z0-9_/]+", target)
        if route_match:
            return f"{self.base_url}{route_match.group(0)}"

        if "dashboard" in target.lower():
            return f"{self.base_url}/"
        if "users/new" in target.lower() or "create user" in target.lower():
            return f"{self.base_url}/users/new"
        if "users" in target.lower():
            return f"{self.base_url}/users"
        if "login" in target.lower():
            return f"{self.base_url}/login"

        return f"{self.base_url}/"

    def _click_by_target(self, target: str) -> None:
        lower_target = target.lower()
        email_match = re.search(r"[\w.+-]+@[\w.-]+", target)
        email = email_match.group(0).lower() if email_match else None

        if target.startswith("/") and " " not in target:
            self.page.goto(self._resolve_url(target), wait_until="domcontentloaded")
            return

        if lower_target.startswith("reset password") and email:
            link = self.page.get_by_role(
                "link",
                name=re.compile(rf"Reset Password.*{re.escape(email)}", re.I),
            ).first
            href = link.get_attribute("href")
            if href:
                self.page.goto(urljoin(self.base_url + "/", href), wait_until="domcontentloaded")
                return
            link.click(timeout=5000)
            return

        if email and "row" in lower_target:
            row = self.page.locator("tbody tr", has_text=email).first
            if row.count() == 0:
                raise RuntimeError(f"Could not find row for {email}")

            if "reset" in lower_target:
                row.get_by_role("button", name=re.compile("Reset Password", re.I)).click()
                return
            if "disable" in lower_target:
                row.get_by_role("button", name=re.compile("Disable User", re.I)).click()
                return
            if "enable" in lower_target:
                row.get_by_role("button", name=re.compile("Enable User", re.I)).click()
                return

        if "reset" in lower_target and email:
            self.page.get_by_role("button", name=re.compile(rf"Reset Password.*{re.escape(email)}", re.I)).first.click(timeout=5000)
            return

        if "disable" in lower_target and email:
            self.page.get_by_role("button", name=re.compile(rf"Disable User.*{re.escape(email)}", re.I)).first.click(timeout=5000)
            return

        if "enable" in lower_target and email:
            self.page.get_by_role("button", name=re.compile(rf"Enable User.*{re.escape(email)}", re.I)).first.click(timeout=5000)
            return

        # Generic fallback: match button or link by visible text.
        try:
            self.page.get_by_role("button", name=target, exact=False).first.click(timeout=5000)
            return
        except Exception:
            pass

        try:
            self.page.get_by_role("link", name=target, exact=False).first.click(timeout=5000)
            return
        except Exception:
            pass

        self.page.locator(f"text={target}").first.click(timeout=5000)

    def _fill_by_target(self, target: str, value: str) -> None:
        try:
            self.page.get_by_label(target, exact=False).first.fill(value)
            return
        except Exception:
            pass

        try:
            self.page.get_by_placeholder(target).first.fill(value)
            return
        except Exception:
            pass

        lowered = target.lower()
        if "name" in lowered:
            self.page.get_by_label("Full Name").fill(value)
            return
        if "email" in lowered:
            self.page.get_by_label("Email").fill(value)
            return
        if "username" in lowered:
            self.page.get_by_label("Username").fill(value)
            return
        if "password" in lowered:
            self.page.get_by_label("Password").fill(value)
            return

        raise RuntimeError(f"Unable to fill target: {target}")

    def _select_by_target(self, target: str, value: str) -> None:
        try:
            self.page.get_by_label(target, exact=False).first.select_option(value=value)
            return
        except Exception:
            pass

        lowered = target.lower()
        if "role" in lowered:
            self.page.get_by_label("Role").select_option(value=value)
            return

        raise RuntimeError(f"Unable to select target: {target}")

    def _execute_step(self, action: str, target: str, value: str) -> None:
        if action == "goto":
            self.page.goto(self._resolve_url(target), wait_until="domcontentloaded")
            return

        if action == "fill":
            self._fill_by_target(target, value)
            return

        if action == "select":
            self._select_by_target(target, value)
            return

        if action == "click":
            self._click_by_target(target)
            return

        if action == "wait":
            timeout_value = 1000
            if value.isdigit():
                timeout_value = int(value)
            self.page.wait_for_timeout(timeout_value)
            return

        raise RuntimeError(f"Unsupported action: {action}")

    def page_text(self) -> str:
        try:
            return self.page.inner_text("body")
        except PlaywrightTimeoutError:
            return ""
