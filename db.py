import sqlite3
import os
import threading

DB_PATH = os.path.join(os.path.dirname(__file__), "aura_users.db")

_db_lock = threading.Lock()

def get_connection():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
        check_same_thread=False
    )
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def get_db_lock():
    return _db_lock
