"""SQLite store shared by the console: sessions, transcripts, memories, the failed
blacklist, and local settings (tokens / team / model config).

One file at ~/.odele-ctf/sessions.db holds everything, created with mode 0600 because
settings may contain API keys and platform tokens. Both the session manager and the
settings store open their own connection to it; SQLite serializes the short writes.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    os.environ.get("ODELE_DB") or (Path.home() / ".odele-ctf" / "sessions.db")
).expanduser()

SCHEMA = """
CREATE TABLE IF NOT EXISTS folders (
    name TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    category TEXT,
    title TEXT,
    folder TEXT,
    status TEXT,
    flag TEXT,
    spec TEXT,
    state TEXT,
    transcript TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_sessions_folder ON sessions(folder);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE TABLE IF NOT EXISTS failed_challenges (
    challenge_id TEXT PRIMARY KEY,
    direction TEXT,
    ts REAL
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY,
    category TEXT,
    title TEXT,
    content TEXT,
    source TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the console database with the full schema applied."""
    path = Path(path) if path else DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.executescript(SCHEMA)
    # migrate older DBs that predate the created_at column
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)")]
    if "created_at" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN created_at REAL")
        conn.commit()
    try:
        os.chmod(path, 0o600)  # settings can hold secrets
    except OSError:
        pass
    return conn


def get_setting(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row[0])
    except (TypeError, json.JSONDecodeError):
        return default


def set_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, json.dumps(value, ensure_ascii=False)),
    )
    conn.commit()
