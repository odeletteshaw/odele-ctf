"""Parent-side session management. Each Session is a challenge solve running in its own
subprocess; the manager spawns them, drains their event queues, and aggregates state so
the view can render a conversation and a rich status panel per session.

Sessions are persisted to SQLite (~/.odele-ctf/sessions.db). Only session metadata is
loaded at startup; transcripts are loaded lazily on selection and saved incrementally,
so a long history no longer forces an 8 MB JSON file to be read and rewritten on every
change."""

import itertools
import json
import multiprocessing as mp
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.worker import worker_main  # noqa: E402

# spawn is the safe start method on macOS (fork + threads is unsafe there).
_CTX = mp.get_context("spawn")

_SCHEMA = """
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
"""


class Session:
    _ids = itertools.count(1)

    def __init__(self, spec: dict[str, Any], title: str, category: str,
                 folder: str | None = None, inherit: "Session | None" = None) -> None:
        self.id = next(Session._ids)
        self.spec = spec
        self.category = category
        self.title = title
        self.folder = folder
        self.events: Any = _CTX.Queue()
        self._guidance: Any = _CTX.Queue()
        self._proc: Any = None  # created in start()
        self.started_at: float | None = None
        self.created_at: float | None = time.time()
        self.transcript: list[dict[str, Any]] = []
        self._loaded = True  # transcript is fully in memory (False for restored sessions)
        self.state: dict[str, Any] = {
            "status": "idle",
            "replies": 0,
            "tool_calls": 0,
            "thinking": "",
            "flag": None,
            "paths": [],
            "tools_used": {},
            "writeup": "",
            "done": False,
        }
        if inherit is not None:
            # A continued session carries the previous attempt's findings forward so the
            # Findings panel isn't blank and the model builds on them instead of redoing them.
            self.state["paths"] = list(inherit.state.get("paths") or [])
            self.state["tools_used"] = dict(inherit.state.get("tools_used") or {})
            note = f"↳ continued from “{inherit.title}” — findings carried over"
            paths = self.state["paths"]
            if paths:
                preview = ", ".join(str(p) for p in paths[:6])
                note += f": {preview}{' …' if len(paths) > 6 else ''}"
            self.transcript.append({"type": "note", "text": note})

    def start(self) -> None:
        self._proc = _CTX.Process(
            target=worker_main, args=(self.spec, self.events, self._guidance), daemon=True
        )
        self.started_at = time.time()
        self.state["status"] = "running"
        self._proc.start()

    def stop(self) -> None:
        """Interrupt the running solve by terminating its subprocess."""
        if self._proc and self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout=3)
            if self._proc.is_alive():
                self._proc.kill()
        self.state["status"] = "cancelled"
        self.state["done"] = True

    def send_guidance(self, text: str) -> None:
        text = text.strip()
        if text:
            self._guidance.put(text)

    def elapsed(self) -> float:
        return 0.0 if self.started_at is None else time.time() - self.started_at

    def is_running(self) -> bool:
        return self.state["status"] == "running" and not self.state["done"]

    def drain(self) -> list[dict[str, Any]]:
        """Pull all pending events from the subprocess; update state and transcript."""
        new: list[dict[str, Any]] = []
        while True:
            try:
                event = self.events.get_nowait()
            except Exception:
                break
            if not isinstance(event, dict):
                continue
            if event.get("type") == "__done__":
                self.state["done"] = True
                continue
            try:
                self._apply(event)
            except Exception:
                pass  # a malformed event must never stop this session's drain
            self.transcript.append(event)
            new.append(event)
        # reap the subprocess once it has finished, so it doesn't linger as a zombie
        if self.state["done"] and self._proc:
            self._proc.join(timeout=0)
        return new

    def _apply(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "agent":
            self.state["thinking"] = event["text"]
            self.state["replies"] += 1
        elif kind == "tool_call":
            self.state["tool_calls"] += 1
            name = event.get("name", "?")
            self.state["tools_used"][name] = self.state["tools_used"].get(name, 0) + 1
            args = event.get("args")
            path = args.get("path") if isinstance(args, dict) else None
            if path and path not in self.state["paths"]:
                self.state["paths"].append(str(path))
        elif kind == "status":
            self.state["status"] = event.get("status", self.state["status"])
            if event.get("flag"):
                self.state["flag"] = event["flag"]
        elif kind == "writeup":
            self.state["writeup"] = event.get("text", "")

    @classmethod
    def from_row(cls, row: tuple) -> "Session":
        """Rebuild a session from a metadata row (no transcript)."""
        s = cls.__new__(cls)
        s.id, s.category, s.title, s.folder, _status, _flag, spec, state, created_at = row
        s.spec = json.loads(spec) if spec else {}
        s.title = s.title or "session"
        s.folder = s.folder
        s.events = None
        s._guidance = None
        s._proc = None
        s.started_at = None
        s.created_at = created_at
        s.transcript = []
        s._loaded = False  # transcript loads lazily on selection
        s.state = json.loads(state) if state else {}
        s.state.setdefault("status", "idle")
        s.state.setdefault("done", True)
        s.state.setdefault("replies", 0)
        s.state.setdefault("tool_calls", 0)
        s.state.setdefault("thinking", "")
        s.state.setdefault("flag", None)
        s.state.setdefault("paths", [])
        s.state.setdefault("tools_used", {})
        s.state.setdefault("writeup", "")
        return s


class Manager:
    """Holds the open sessions, their folders, and which session is active."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else (Path.home() / ".odele-ctf" / "sessions.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path))
        self._db.executescript(_SCHEMA)
        # migrate older DBs that predate the created_at column
        cols = [r[1] for r in self._db.execute("PRAGMA table_info(sessions)")]
        if "created_at" not in cols:
            self._db.execute("ALTER TABLE sessions ADD COLUMN created_at REAL")
        self.sessions: list[Session] = []
        self.folders: list[str] = []
        self.active: Session | None = None
        self._load()

    def _load(self) -> None:
        self.folders = [r[0] for r in self._db.execute("SELECT name FROM folders")]
        rows = self._db.execute(
            "SELECT id, category, title, folder, status, flag, spec, state, created_at "
            "FROM sessions ORDER BY id"
        ).fetchall()
        for row in rows:
            try:
                self.sessions.append(Session.from_row(row))
            except Exception:
                continue
        if self.sessions:
            Session._ids = itertools.count(max(s.id for s in self.sessions) + 1)

    def load_transcript(self, session: Session) -> list[dict[str, Any]]:
        """Load a restored session's transcript from the DB on first selection."""
        if session._loaded:
            return session.transcript
        row = self._db.execute(
            "SELECT transcript FROM sessions WHERE id=?", (session.id,)
        ).fetchone()
        if row and row[0]:
            session.transcript = json.loads(row[0])
        session._loaded = True
        return session.transcript

    def save(self) -> None:
        """Persist sessions and folders incrementally (upsert, no full-file rewrite)."""
        for s in self.sessions:
            if s._loaded:
                self._db.execute(
                    "INSERT OR REPLACE INTO sessions "
                    "(id, category, title, folder, status, flag, spec, state, transcript, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (s.id, s.category, s.title, s.folder,
                     s.state.get("status"), s.state.get("flag"),
                     json.dumps(s.spec, ensure_ascii=False),
                     json.dumps(s.state, ensure_ascii=False),
                     json.dumps(s.transcript, ensure_ascii=False),
                     s.created_at),
                )
            else:
                # Never clobber a transcript we haven't loaded into memory yet.
                self._db.execute(
                    "UPDATE sessions SET category=?, title=?, folder=?, status=?, flag=?, "
                    "spec=?, state=? WHERE id=?",
                    (s.category, s.title, s.folder,
                     s.state.get("status"), s.state.get("flag"),
                     json.dumps(s.spec, ensure_ascii=False),
                     json.dumps(s.state, ensure_ascii=False), s.id),
                )
        self._db.execute("DELETE FROM folders")
        self._db.executemany(
            "INSERT OR IGNORE INTO folders (name) VALUES (?)", [(f,) for f in self.folders]
        )
        self._db.commit()

    def new_folder(self, name: str) -> bool:
        name = name.strip()
        if name and name not in self.folders:
            self.folders.append(name)
            self.save()
            return True
        return False

    def delete_folder(self, name: str) -> None:
        """Delete a folder and all its sessions."""
        if name not in self.folders:
            return
        self.folders.remove(name)
        doomed = [s for s in self.sessions if s.folder == name]
        for s in doomed:
            if s.is_running():
                s.stop()
            if s in self.sessions:
                self.sessions.remove(s)
            if self.active is s:
                self.active = None
            self._db.execute("DELETE FROM sessions WHERE id=?", (s.id,))
        self.save()

    def new_session(self, spec: dict[str, Any], title: str, category: str,
                    folder: str | None = None, inherit: Session | None = None) -> Session:
        session = Session(spec, title, category, folder=folder, inherit=inherit)
        self.sessions.append(session)
        self.active = session
        session.start()
        self.save()
        return session

    def new_pending_session(self, spec: dict[str, Any], title: str, category: str,
                            folder: str | None = None) -> Session:
        """Create a placeholder session that is visible but not yet solving; its spec can be
        filled in and started later with start_solve()."""
        session = Session(spec, title, category, folder=folder)
        session.state["status"] = "preparing"
        self.sessions.append(session)
        self.active = session
        self.save()
        return session

    def start_pending_session(self, session: Session, spec: dict[str, Any]) -> None:
        """Give a placeholder session its real spec and start solving it."""
        session.spec = spec
        session.state["status"] = "running"
        session.start()
        self.save()

    def rename(self, session: Session, title: str) -> None:
        title = title.strip()
        if title:
            session.title = title
            self.save()

    def stop(self, session: Session) -> None:
        session.stop()
        self.save()

    def stop_all(self) -> None:
        """Stop every running session (used on shutdown to avoid orphaned workers)."""
        for session in self.sessions:
            if session.is_running():
                session.stop()
        self.save()

    def delete(self, session: Session) -> None:
        """Remove a session and its subprocess; stops it first if still running."""
        if session.is_running():
            session.stop()
        if session in self.sessions:
            self.sessions.remove(session)
        if self.active is session:
            self.active = None
        self._db.execute("DELETE FROM sessions WHERE id=?", (session.id,))
        self.save()

    def add_failed(self, challenge_id: str, direction: str | None = None) -> None:
        """Persist a challenge the agent failed to solve so autosolve skips it next time."""
        self._db.execute(
            "INSERT OR REPLACE INTO failed_challenges (challenge_id, direction, ts) VALUES (?,?,?)",
            (str(challenge_id), direction, time.time()),
        )
        self._db.commit()

    def failed_ids(self) -> set[str]:
        return {r[0] for r in self._db.execute("SELECT challenge_id FROM failed_challenges")}

    def remove_failed(self, challenge_id: str) -> None:
        """Allow a specific challenge to be retried by removing it from the blacklist."""
        self._db.execute("DELETE FROM failed_challenges WHERE challenge_id=?", (str(challenge_id),))
        self._db.commit()

    def clear_failed(self) -> None:
        self._db.execute("DELETE FROM failed_challenges")
        self._db.commit()

    def drain_all(self) -> None:
        for session in self.sessions:
            was_done = session.state["done"]
            session.drain()
            if not was_done and session.state["done"]:
                self.save()  # persist the finalized transcript/status
