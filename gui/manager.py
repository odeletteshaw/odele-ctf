"""Parent-side session management. Each Session is a challenge solve running in its own
subprocess; the manager spawns them, drains their event queues, and aggregates state so
the view can render a conversation and a rich status panel per session.
"""

import itertools
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

    def __init__(self, spec: dict[str, Any], title: str, category: str) -> None:
        self.id = next(Session._ids)
        self.spec = spec
        self.category = category
        self.title = title
        self.events: Any = _CTX.Queue()
        self._guidance: Any = _CTX.Queue()
        self._proc = _CTX.Process(
            target=worker_main, args=(spec, self.events, self._guidance), daemon=True
        )
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
        self.started_at = time.time()
        self.state["status"] = "running"
        self._proc.start()

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


class Manager:
    """Holds the open sessions and which one is active (shown in the center pane)."""

    def __init__(self) -> None:
        self.sessions: list[Session] = []
        self.active: Session | None = None

    def new_session(self, spec: dict[str, Any], title: str, category: str) -> Session:
        session = Session(spec, title, category)
        self.sessions.append(session)
        self.active = session
        session.start()
        return session

    def drain_all(self) -> None:
        for session in self.sessions:
            session.drain()
