import threading
import queue
from db import get_connection
_history_queue = queue.Queue()
_worker_started = False

def _history_worker():
    """Single background DB writer (ONLY writer thread)"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_command TEXT,
                aura_response TEXT,
                input_mode TEXT DEFAULT 'text',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        print("TABLE CREATION ERROR:", e)

    while True:
        item = _history_queue.get()
        if item is None:
            break  # graceful shutdown

        user_id, user_text, bot_text, input_mode = item

        try:
            cursor.execute("""
                INSERT INTO command_history
                (user_id, user_command, aura_response, input_mode)
                VALUES (?, ?, ?, ?)
            """, (user_id, user_text, bot_text, input_mode))
            conn.commit()
        except Exception as e:
            print("SAVE_HISTORY ERROR:", e)

        _history_queue.task_done()

    cursor.close()
    conn.close()

def save_history(user_id, user_text, bot_text, input_mode="text"):
    """Public API — non-blocking, safe from ANY thread"""
    global _worker_started

    if not _worker_started:
        t = threading.Thread(target=_history_worker, daemon=True)
        t.start()
        _worker_started = True

    _history_queue.put((user_id, user_text, bot_text, input_mode))
    return True
