import json
import os
import sqlite3
import threading
from datetime import datetime
from functools import lru_cache

DB_PATH = "workspace/gyansutr.db"
_DB_LOCK = threading.RLock()


@lru_cache(maxsize=4)
def get_sqlite_connection(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    return sqlite3.connect(db_path, check_same_thread=False)


def _ensure_column(cursor, table, name, declaration):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    if name not in existing:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def init_db():
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS notes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  title TEXT,
                  content TEXT,
                  updated_at TEXT)"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS chat_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT,
                  content TEXT,
                  sources TEXT,
                  created_at TEXT,
                  thread_id TEXT DEFAULT 'default')"""
        )
        _ensure_column(c, "chat_history", "persona", "TEXT")
        conn.commit()


def save_note(note_id, title, content):
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if note_id:
            c.execute("UPDATE notes SET title=?, content=?, updated_at=? WHERE id=?", (title, content, timestamp, note_id))
        else:
            c.execute("INSERT INTO notes (title, content, updated_at) VALUES (?, ?, ?)", (title, content, timestamp))
            note_id = c.lastrowid
        conn.commit()
        return note_id


def get_notes_list():
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, title, updated_at FROM notes ORDER BY updated_at DESC")
        rows = c.fetchall()
    return [{"id": r[0], "title": r[1], "updated_at": r[2]} for r in rows]


def get_note(note_id):
    if not note_id:
        return None
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, title, content, updated_at FROM notes WHERE id=?", (note_id,))
        row = c.fetchone()
    if row:
        return {"id": row[0], "title": row[1], "content": row[2], "updated_at": row[3]}
    return None


def save_chat_message(role, content, sources=None, thread_id="default", persona=None):
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO chat_history (role, content, sources, created_at, thread_id, persona) VALUES (?, ?, ?, ?, ?, ?)",
            (role, content, json.dumps(sources or []), timestamp, thread_id, persona),
        )
        conn.commit()


def get_chat_history(limit=200, thread_id="default"):
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT role, content, sources, created_at, persona FROM chat_history WHERE thread_id=? ORDER BY id ASC LIMIT ?",
            (thread_id, limit),
        )
        rows = c.fetchall()
    history = []
    for role, content, sources, created_at, persona in rows:
        history.append({
            "role": role,
            "content": content,
            "sources": json.loads(sources) if sources else [],
            "timestamp": created_at,
            "persona": persona,
        })
    return history


def clear_chat_history(thread_id="default"):
    with _DB_LOCK:
        conn = get_sqlite_connection(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM chat_history WHERE thread_id=?", (thread_id,))
        conn.commit()