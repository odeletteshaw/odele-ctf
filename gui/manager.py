"""Parent-side session management. Each Session is a challenge solve running in its own
subprocess; the manager spawns them, drains their event queues, and aggregates state so
the view can render a conversation and a rich status panel per session.

Sessions and folders are persisted to a JSON file (~/.odele-ctf/sessions.json) so they
survive GUI restarts. A restored session is "done" (its subprocess is gone) but keeps its
transcript, findings, and flag."""

import itertools
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.worker import worker_main  # noqa: E402

# spawn is the safe start method on macOS (fork + threads is unsafe there).
_CTX = mp.get_context("spawn")


class Session:
    _ids = itertools.count(1)

    def __init__(self, spec: dict[str, Any], title: str, category: str,
                 folder: str | None = None) -> None:
        self.id = next(Session._ids)
        self.spec = spec
        self.category = category
        self.title = title
        self.folder = folder
        self.events: Any = _CTX.Queue()
        self._guidance: Any = _CTX.Queue()
        self._proc: Any = None  # created in start()
        self.started_at: float | None = None
        self.transcript: list[dict[str, Any]] = []
        self.state: dict[str, Any] = {
            "status": "idle",
            "replies": 0,
            "tool_calls": 0,
            "thinking": "",
            "flag": None,
            "paths": [],
            "tools_used": {},
            "done": False,
        }

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
            if event.get("type") == "__done__":
                self.state["done"] = True
                continue
            self._apply(event)
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
            path = (event.get("args") or {}).get("path")
            if path and path not in self.state["paths"]:
                self.state["paths"].append(path)
        elif kind == "status":
            self.state["status"] = event.get("status", self.state["status"])
            if event.get("flag"):
                self.state["flag"] = event["flag"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "spec": self.spec,
            "title": self.title,
            "category": self.category,
            "folder": self.folder,
            "transcript": self.transcript,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Session":
        s = cls.__new__(cls)
        s.id = d["id"]
        s.spec = d["spec"]
        s.title = d["title"]
        s.category = d["category"]
        s.folder = d.get("folder")
        s.events = None
        s._guidance = None
        s._proc = None
        s.started_at = None
        s.transcript = d.get("transcript", [])
        st = d.get("state", {})
        s.state = {
            "status": st.get("status", "idle"),
            "replies": st.get("replies", 0),
            "tool_calls": st.get("tool_calls", 0),
            "thinking": st.get("thinking", ""),
            "flag": st.get("flag"),
            "paths": st.get("paths", []),
            "tools_used": st.get("tools_used", {}),
            "done": True,  # a restored session is not running
        }
        return s


class Manager:
    """Holds the open sessions, their folders, and which session is active."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else (Path.home() / ".odele-ctf" / "sessions.json")
        self.sessions: list[Session] = []
        self.folders: list[str] = []
        self.active: Session | None = None
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return
        self.folders = data.get("folders", [])
        for d in data.get("sessions", []):
            try:
                self.sessions.append(Session.from_dict(d))
            except Exception:
                continue
        if self.sessions:
            Session._ids = itertools.count(max(s.id for s in self.sessions) + 1)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "folders": self.folders,
            "sessions": [s.to_dict() for s in self.sessions],
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def new_folder(self, name: str) -> bool:
        name = name.strip()
        if name and name not in self.folders:
            self.folders.append(name)
            self.save()
            return True
        return False

    def new_session(self, spec: dict[str, Any], title: str, category: str,
                    folder: str | None = None) -> Session:
        session = Session(spec, title, category, folder=folder)
        self.sessions.append(session)
        self.active = session
        session.start()
        self.save()
        return session

    def rename(self, session: Session, title: str) -> None:
        title = title.strip()
        if title:
            session.title = title
            self.save()

    def stop(self, session: Session) -> None:
        session.stop()
        self.save()

    def drain_all(self) -> None:
        for session in self.sessions:
            was_done = session.state["done"]
            session.drain()
            if not was_done and session.state["done"]:
                self.save()  # persist the finalized transcript/status
