import os
import random
import sqlite3
import string
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-me"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def log_activity(message: str) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO activity_log (message, created_at) VALUES (?, ?)",
        (message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    db.commit()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            password TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        seed_users = [
            ("John Smith", "john@company.com", "user", "Active"),
            ("Alice Johnson", "alice@company.com", "admin", "Active"),
            ("Bob Lee", "bob@company.com", "viewer", "Active"),
            ("Carol White", "carol@company.com", "user", "Active"),
            ("Dave Brown", "dave@company.com", "viewer", "Disabled"),
        ]
        cur.executemany(
            "INSERT INTO users (full_name, email, role, status) VALUES (?, ?, ?, ?)",
            seed_users,
        )
        cur.execute(
            "INSERT INTO activity_log (message, created_at) VALUES (?, ?)",
            (
                "Seeded initial users.",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    db.commit()
    db.close()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == "admin" and password == "admin123":
            session["logged_in"] = True
            log_activity("Admin logged in.")
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials. Try admin / admin123.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    db = get_db()
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    recent_activity = db.execute(
        "SELECT message, created_at FROM activity_log ORDER BY id DESC LIMIT 10"
    ).fetchall()
    return render_template(
        "dashboard.html",
        total_users=total_users,
        recent_activity=recent_activity,
    )


@app.route("/users")
@login_required
def users_list():
    db = get_db()
    users = db.execute(
        "SELECT id, full_name, email, role, status FROM users ORDER BY id"
    ).fetchall()
    return render_template("users.html", users=users)


@app.route("/users/new", methods=["GET", "POST"])
@login_required
def create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", "user").strip().lower()

        if not full_name or not email or role not in {"user", "admin", "viewer"}:
            flash("Please provide valid full name, email, and role.", "error")
            return render_template("new_user.html")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (full_name, email, role, status) VALUES (?, ?, ?, 'Active')",
                (full_name, email, role),
            )
            db.commit()
            log_activity(f"Created user {email} with role {role}.")
            flash(f"User {email} created successfully.", "success")
            return redirect(url_for("users_list"))
        except sqlite3.IntegrityError:
            flash(f"User with email {email} already exists.", "error")

    return render_template("new_user.html")


@app.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
def reset_password(user_id: int):
    db = get_db()
    user = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("users_list"))

    if request.method == "GET":
        return render_template("reset_password.html", user=user)

    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not new_password or new_password != confirm_password:
        flash("Please enter matching new password and confirmation.", "error")
        return render_template("reset_password.html", user=user)

    db.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
    db.commit()
    log_activity(f"Reset password for {user['email']}.")
    flash(f"Password reset for {user['email']}. New password: {new_password}", "success")
    return redirect(url_for("users_list"))


@app.post("/users/<int:user_id>/toggle-status")
@login_required
def toggle_status(user_id: int):
    db = get_db()
    user = db.execute(
        "SELECT email, status FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("users_list"))

    new_status = "Disabled" if user["status"] == "Active" else "Active"
    db.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    db.commit()
    log_activity(f"Changed status for {user['email']} to {new_status}.")
    flash(f"User {user['email']} is now {new_status}.", "success")
    return redirect(url_for("users_list"))


init_db()

if __name__ == "__main__":
    app.run(port=5050, debug=False)
