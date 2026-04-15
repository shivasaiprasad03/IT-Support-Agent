import sys
import threading
import time

from dotenv import load_dotenv

from admin_panel.app import app as flask_app
from agent.browser_agent import BrowserAgent
from agent.task_router import handle_task


def run_flask() -> None:
    flask_app.run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)


def main() -> None:
    load_dotenv()

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)

    try:
        agent = BrowserAgent(base_url="http://localhost:5050")
    except Exception as exc:
        print(f"Failed to start browser agent: {exc}")
        sys.exit(1)

    print("IT Support Agent ready. Type your request (or 'quit' to exit):")

    try:
        while True:
            task = input("\n> ").strip()
            if not task:
                continue
            if task.lower() == "quit":
                break

            print("[Agent] Planning...")
            try:
                result = handle_task(task, agent)
                print(f"[Agent] Done: {result}")
            except Exception as exc:
                print(f"[Agent] Error: {exc}")
    finally:
        agent.close()
        print("Agent closed. Goodbye.")


if __name__ == "__main__":
    main()
