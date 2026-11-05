from db import get_connection
import hashlib
import re
import sqlite3
import os
import json
import smtplib
from email.mime.text import MIMEText

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()

def validate_name(name: str):
    n = (name or "").strip()
    if not n:
        return False, "Name is required."
    if len(n) < 2:
        return False, "Name must be at least 2 characters."
    if len(n) > 80:
        return False, "Name is too long."
    if not re.match(r"^[A-Za-z][A-Za-z\s.'-]*$", n):
        return False, "Name contains invalid characters."
    return True, ""

def validate_email(email: str):
    e = normalize_email(email)
    if not e:
        return False, "Email is required.", e
    if len(e) > 254:
        return False, "Email is too long.", e
    if not EMAIL_RE.match(e):
        return False, "Invalid email format.", e
    return True, "", e

def validate_password(password: str):
    p = password or ""
    if not p:
        return False, "Password is required."
    if len(p) < 8:
        return False, "Password must be at least 8 characters."
    if len(p) > 128:
        return False, "Password is too long."
    if not re.search(r"[A-Za-z]", p):
        return False, "Password must include at least one letter."
    if not re.search(r"\d", p):
        return False, "Password must include at least one number."
    return True, ""

def hash_password(password):
    return hashlib.sha256((password or "").encode()).hexdigest()

def _ensure_users_table(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("PRAGMA table_info(users)")
    cols = {row[1] for row in cursor.fetchall()}
    if "role" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "is_active" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

def register_user(name, email, password):
    valid_name, msg = validate_name(name)
    if not valid_name:
        return False, msg

    valid_email, msg, email_n = validate_email(email)
    if not valid_email:
        return False, msg

    valid_pwd, msg = validate_password(password)
    if not valid_pwd:
        return False, msg

    try:
        conn = get_connection()
        cursor = conn.cursor()
        _ensure_users_table(cursor)
        cursor.execute("SELECT 1 FROM users WHERE email=?", (email_n,))
        if cursor.fetchone():
            conn.close()
            return False, "An account with this email already exists."

        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (name.strip(), email_n, hash_password(password), "user", 1))

        conn.commit()
        conn.close()
        return True, "Registration successful"

    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."
    except Exception as e:
        return False, str(e)

def login_user(email, password):
    valid_email, msg, email_n = validate_email(email)
    if not valid_email:
        return False, msg, None, None

    pwd = password or ""
    if not pwd:
        return False, "Password is required.", None, None
    if len(pwd) > 128:
        return False, "Password is too long.", None, None

    conn = get_connection()
    cursor = conn.cursor()
    _ensure_users_table(cursor)

    cursor.execute("""
        SELECT user_id, name, password_hash, role, is_active
        FROM users
        WHERE email=?
    """, (email_n,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, "User not found", None, None

    user_id, name, pwd_hash, _role, is_active = row
    if int(is_active or 0) != 1:
        return False, "Account is disabled. Contact administrator.", None, None
    if pwd_hash != hash_password(password):
        return False, "Invalid password", None, None

    return True, "Login success", user_id, name

def login_user_with_hash(email, password_hash_value):
    """Login using a precomputed password hash (for local auto-login session restore)."""
    valid_email, msg, email_n = validate_email(email)
    if not valid_email:
        return False, msg, None, None

    ph = (password_hash_value or "").strip()
    if not ph:
        return False, "Session credential is missing.", None, None

    conn = get_connection()
    cursor = conn.cursor()
    _ensure_users_table(cursor)

    cursor.execute(
        """
        SELECT user_id, name, password_hash, role, is_active
        FROM users
        WHERE email=?
        """,
        (email_n,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, "User not found", None, None

    user_id, name, pwd_hash, _role, is_active = row
    if int(is_active or 0) != 1:
        return False, "Account is disabled. Contact administrator.", None, None
    if pwd_hash != ph:
        return False, "Session credential is invalid.", None, None

    return True, "Login success", user_id, name

def get_user_role(email):
    """Return user's role by email, defaulting to 'user'."""
    valid_email, _, email_n = validate_email(email)
    if not valid_email:
        return "user"
    admins_env = os.getenv("AURA_ADMIN_EMAILS", "")
    if admins_env:
        admins = {e.strip().lower() for e in admins_env.split(",") if e.strip()}
        if email_n in admins:
            return "admin"
    try:
        conn = get_connection()
        cursor = conn.cursor()
        _ensure_users_table(cursor)
        cursor.execute("SELECT role FROM users WHERE email=?", (email_n,))
        row = cursor.fetchone()
        conn.close()
        if row and isinstance(row[0], str) and row[0].strip():
            return row[0].strip().lower()
        return "user"
    except Exception:
        return "user"

def _load_email_config():
    env_email = (os.getenv("AURA_SENDER_EMAIL", "") or os.getenv("SENDER_EMAIL", "")).strip()
    env_pass = (os.getenv("AURA_SENDER_APP_PASSWORD", "") or os.getenv("SENDER_PASSWORD", "")).strip()
    if env_email and env_pass:
        return {
            "smtp_server": (os.getenv("AURA_SMTP_SERVER", "") or os.getenv("SMTP_SERVER", "smtp.gmail.com")).strip() or "smtp.gmail.com",
            "smtp_port": int((os.getenv("AURA_SMTP_PORT", "") or os.getenv("SMTP_PORT", "587")) or "587"),
            "sender_email": env_email,
            "sender_password": env_pass,
        }
    try:
        with open("data/email_config.json", "r") as f:
            return json.load(f)
    except Exception:
        return {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "your_email@gmail.com",
            "sender_password": "your_app_password",
        }

def send_password_reset_otp(to_email: str, otp_code: str):
    """Send OTP email for password reset."""
    cfg = _load_email_config()
    sender = str(cfg.get("sender_email", "")).strip()
    password = str(cfg.get("sender_password", "")).strip()
    if sender in {"", "your_email@gmail.com"} or password in {"", "your_app_password"}:
        return False, "Email sender is not configured. Set Gmail app password in data/email_config.json."

    try:
        msg = MIMEText(
            (
                "Your AURA password reset code is: "
                f"{otp_code}\n\n"
                "This code expires in 10 minutes. If you did not request this, ignore this email."
            )
        )
        msg["Subject"] = "AURA Password Reset OTP"
        msg["From"] = sender
        msg["To"] = to_email

        server = smtplib.SMTP(cfg.get("smtp_server", "smtp.gmail.com"), int(cfg.get("smtp_port", 587)))
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, [to_email], msg.as_string())
        server.quit()
        return True, "OTP sent successfully."
    except Exception as e:
        return False, f"Failed to send OTP: {str(e)[:80]}"

def reset_password(email, new_password):
    """Reset password for an existing account."""
    valid_email, msg, email_n = validate_email(email)
    if not valid_email:
        return False, msg

    valid_pwd, msg = validate_password(new_password)
    if not valid_pwd:
        return False, msg

    try:
        conn = get_connection()
        cursor = conn.cursor()
        _ensure_users_table(cursor)

        cursor.execute("SELECT user_id FROM users WHERE email=?", (email_n,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "No account found for this email."

        cursor.execute(
            "UPDATE users SET password_hash=? WHERE email=?",
            (hash_password(new_password), email_n),
        )
        conn.commit()
        conn.close()
        return True, "Password reset successful. Please sign in with your new password."
    except Exception as e:
        return False, str(e)
