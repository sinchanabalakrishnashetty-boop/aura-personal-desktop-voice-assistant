import argparse
import json
import os
import sys


def cmd_list_mics() -> int:
    try:
        import sounddevice as sd
        import speech_recognition as sr
    except Exception as exc:
        print(f"Dependency error: {exc}")
        return 1

    print(f"sd.default: {sd.default.device}")
    devs = sd.query_devices()
    for i, d in enumerate(devs):
        if d.get("max_input_channels", 0) > 0:
            print(f"{i}: {d['name']} | in={d['max_input_channels']} | sr={d['default_samplerate']}")

    print("--- speech_recognition ---")
    for i, n in enumerate(sr.Microphone.list_microphone_names()):
        print(f"{i}: {n}")

    return 0


def cmd_calibrate_mics() -> int:
    try:
        import numpy as np
        import speech_recognition as sr
    except Exception as exc:
        print(f"Dependency error: {exc}")
        return 1

    candidates = [1, 5, 9, 18, 14, 0, 4]
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.pause_threshold = 0.9

    results = []
    for idx in candidates:
        print(f"\n=== Testing mic index {idx} ===")
        try:
            with sr.Microphone(device_index=idx) as src:
                print("Calibrating...")
                r.adjust_for_ambient_noise(src, duration=0.6)
                print(f"Energy threshold: {r.energy_threshold:.1f}")
                print("Speak now: 'open chrome' (within 5 sec)")
                try:
                    audio = r.listen(src, timeout=5, phrase_time_limit=3.5)
                except Exception as exc:
                    print(f"No speech: {exc}")
                    results.append((idx, 0.0, ""))
                    continue

            raw = audio.get_raw_data()
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(np.square(arr)))) if arr.size else 0.0
            text = ""
            try:
                text = (r.recognize_google(audio, language="en-US") or "").strip().lower()
                print(f"Heard: {text}")
            except Exception as exc:
                print(f"Recognize failed: {exc}")
            print(f"RMS: {rms:.6f}")
            results.append((idx, rms, text))
        except Exception as exc:
            print(f"Mic {idx} failed: {exc}")
            results.append((idx, 0.0, ""))

    score = []
    for idx, rms, text in results:
        recog = 1 if text else 0
        cmd = 2 if ("open" in text or "chrome" in text) else 0
        score.append((cmd + recog, rms, idx, text))
    score.sort(reverse=True)

    print("\n=== Ranked ===")
    for s, rms, idx, text in score:
        print(f"idx={idx} score={s} rms={rms:.6f} text='{text}'")

    best = score[0][2] if score else None
    print(f"\nBEST_INDEX={best}")
    return 0


def cmd_test_mic(index: int) -> int:
    try:
        import numpy as np
        import speech_recognition as sr
    except Exception as exc:
        print(f"Dependency error: {exc}")
        return 1

    r = sr.Recognizer()
    r.pause_threshold = 1.0
    r.energy_threshold = 120
    r.dynamic_energy_threshold = True

    print(f"test mic {index}")
    with sr.Microphone(device_index=index) as src:
        r.adjust_for_ambient_noise(src, duration=1.0)
        print("say now: open chrome")
        audio = r.listen(src, timeout=8, phrase_time_limit=5)

    raw = audio.get_raw_data()
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    print("rms", float(np.sqrt(np.mean(np.square(arr)))))
    try:
        t = r.recognize_google(audio, language="en-IN")
        print("text", t)
    except Exception as exc:
        print("exc_type", type(exc).__name__)
        print("exc_repr", repr(exc))

    return 0


def _load_gmail_config() -> dict:
    cfg = {
        "enabled": True,
        "credentials_file": "credentials.json",
        "token_file": "token.json",
    }

    cfg_path = os.path.join("data", "email_config.json")
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                gmail_cfg = raw.get("gmail_api") if isinstance(raw.get("gmail_api"), dict) else raw
                if "enabled" in gmail_cfg:
                    cfg["enabled"] = bool(gmail_cfg["enabled"])
                if gmail_cfg.get("credentials_file"):
                    cfg["credentials_file"] = str(gmail_cfg["credentials_file"]).strip()
                if gmail_cfg.get("token_file"):
                    cfg["token_file"] = str(gmail_cfg["token_file"]).strip()
        except Exception as exc:
            print(f"Warning: failed to read {cfg_path}: {exc}")

    cfg["credentials_file"] = (
        os.getenv("AURA_GMAIL_CREDENTIALS_FILE")
        or os.getenv("GMAIL_CREDENTIALS_FILE")
        or cfg["credentials_file"]
    )
    cfg["token_file"] = (
        os.getenv("AURA_GMAIL_TOKEN_FILE")
        or os.getenv("GMAIL_TOKEN_FILE")
        or cfg["token_file"]
    )

    return cfg


def cmd_generate_token() -> int:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except Exception:
        print("Missing Google OAuth dependencies.")
        print("Install with: pip install google-auth google-auth-oauthlib google-api-python-client")
        return 1

    scopes = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/contacts.readonly",
    ]

    cfg = _load_gmail_config()
    credentials_file = cfg["credentials_file"]
    token_file = cfg["token_file"]

    if not cfg.get("enabled", True):
        print("Gmail API is disabled in config (gmail_api.enabled=false).")
        return 1

    if not os.path.exists(credentials_file):
        print(f"Credentials file not found: {credentials_file}")
        print("Place your OAuth client credentials JSON at that path and run again.")
        return 1

    creds = None
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, scopes)
        except Exception:
            creds = None

    if creds and os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as fh:
                tok_data = json.load(fh)
            granted = set(tok_data.get("scopes", []))
            needed = set(scopes)
            if not needed.issubset(granted):
                missing = needed - granted
                print(f"Token is missing scopes: {', '.join(sorted(missing))}")
                print("Re-authorising to grant additional permissions...")
                creds = None
        except Exception:
            creds = None

    if creds and creds.valid:
        print(f"Token already valid: {token_file}")
        return 0

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
        creds = flow.run_local_server(port=0)

    token_parent = os.path.dirname(token_file)
    if token_parent:
        os.makedirs(token_parent, exist_ok=True)

    with open(token_file, "w", encoding="utf-8") as token:
        token.write(creds.to_json())

    print(f"Token generated successfully: {token_file}")
    return 0


def cmd_init_db() -> int:
    try:
        import mysql.connector
        from dotenv import load_dotenv
    except Exception as exc:
        print(f"Dependency error: {exc}")
        return 1

    load_dotenv()

    db_host = os.getenv("DB_HOST", "localhost")
    db_user = os.getenv("DB_USER", "root")
    db_password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "aura_db")

    try:
        conn = mysql.connector.connect(host=db_host, user=db_user, password=db_password)
        cursor = conn.cursor()
        print(f"Checking for database '{db_name}'...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cursor.execute(f"USE {db_name}")

        sql_file_path = "SQL.sql"
        if not os.path.exists(sql_file_path):
            print(f"Error: {sql_file_path} not found.")
            return 1

        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        commands = sql_script.split(";")
        for command in commands:
            cmd = command.strip()
            if cmd and not cmd.startswith("--"):
                if "CREATE DATABASE" in cmd.upper() or "USE " in cmd.upper():
                    continue
                print(f"Executing: {cmd[:50]}...")
                cursor.execute(cmd)

        conn.commit()
        print("SUCCESS: Database initialized successfully!")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    finally:
        if "conn" in locals() and conn.is_connected():
            cursor.close()
            conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="project_tools.py")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-mics")
    sub.add_parser("calibrate-mics")

    p_test = sub.add_parser("test-mic")
    p_test.add_argument("--index", type=int, default=1)

    sub.add_parser("generate-token")
    sub.add_parser("init-db")

    args = parser.parse_args()

    if args.command == "list-mics":
        return cmd_list_mics()
    if args.command == "calibrate-mics":
        return cmd_calibrate_mics()
    if args.command == "test-mic":
        return cmd_test_mic(args.index)
    if args.command == "generate-token":
        return cmd_generate_token()
    if args.command == "init-db":
        return cmd_init_db()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
