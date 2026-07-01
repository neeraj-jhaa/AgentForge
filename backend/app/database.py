"""
Lightweight persistence layer (stdlib sqlite3 - zero extra services to run).

Stores every task, its plan, every agent event (for audit / replay) and the
final result, so the frontend can reload history after a refresh.
"""
import sqlite3
import json
import time
import uuid
from contextlib import contextmanager
from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def create_task(goal: str) -> str:
    task_id = str(uuid.uuid4())[:8]
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tasks (id, goal, status, created_at, updated_at) VALUES (?,?,?,?,?)",
            (task_id, goal, "running", now, now),
        )
    return task_id


def update_task_status(task_id: str, status: str, result: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status=?, result=?, updated_at=? WHERE id=?",
            (status, result, time.time(), task_id),
        )


def log_event(task_id: str, agent: str, kind: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (task_id, agent, kind, content, created_at) VALUES (?,?,?,?,?)",
            (task_id, agent, kind, content, time.time()),
        )


def add_memory(task_id: str, text: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memory (task_id, text, created_at) VALUES (?,?,?)",
            (task_id, text, time.time()),
        )


def all_memory() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT text FROM memory ORDER BY id DESC LIMIT 500").fetchall()
    return [r["text"] for r in rows]


def list_tasks() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50").fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        events = conn.execute(
            "SELECT * FROM events WHERE task_id=? ORDER BY id ASC", (task_id,)
        ).fetchall()
    d = dict(row)
    d["events"] = [dict(e) for e in events]
    return d
