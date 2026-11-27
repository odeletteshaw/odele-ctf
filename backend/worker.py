"""Subprocess entry point for one session. Runs the solve for a task spec and streams
structured events back to the parent over `events_q`; reads supervisor guidance from
`guidance_q`. Each session lives in its own process, so a crash or hang is contained.
"""

import importlib
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.loop import generate_writeup, solve  # noqa: E402
from agent.taskbuilder import build_task  # noqa: E402
from agent.team import run_team  # noqa: E402


def worker_main(spec: dict[str, Any], events_q: Any, guidance_q: Any,
                approvals_q: Any = None, replies_q: Any = None) -> None:
    events_log: list[dict[str, Any]] = []

    def on_event(event: dict[str, Any]) -> None:
        events_log.append(event)
        events_q.put(event)

    def guidance() -> str | None:
        try:
            return guidance_q.get_nowait()
        except Exception:
            return None

    # Real targets may not use flag{...}; honor a custom prefix.
    pattern = None
    if spec.get("kind") == "custom":
        prefix = spec.get("flag_prefix") or "flag"
        pattern = re.compile(re.escape(prefix) + r"\{[^}\n\"']+\}")

    cleanup = lambda: None  # noqa: E731
    try:
        known_flag, tools, system, user, cleanup = build_task(spec)
        if spec.get("context"):
            user = spec["context"] + "\n\n---\n\n" + user
        # Category-specific "when stuck" checklist, injected by run_loop on repeated calls.
        category = spec.get("category") or "web"
        diagnostic = None
        try:
            diagnostic = getattr(importlib.import_module(f"agent.categories.{category}.agent"), "DIAGNOSTIC", None)
        except Exception:
            diagnostic = None
        events_q.put({"type": "status", "status": "running"})
        # The GUI passes a per-session turn budget (default 100). Custom targets also get
        # persist=True so the agent keeps going on text without a flag.
        max_turns = int(spec.get("max_turns", 100))
        report = ""
        if spec.get("team"):
            def ask_user_callback(request: dict[str, Any]) -> str:
                """Emit an @mention and block until the user replies on the Calls page."""
                if replies_q is None:
                    return "No user is attached to this run; proceed with best effort."
                events_q.put({"type": "mention", "status": "pending", **request})
                deadline = time.time() + 300
                while time.time() < deadline:
                    try:
                        text = replies_q.get(timeout=1)
                    except Exception:
                        continue
                    events_q.put({"type": "mention", "status": "answered",
                                  "reply": text, **request})
                    return text
                events_q.put({"type": "mention", "status": "timeout", **request})
                return "No reply from the user (timeout); proceed with best effort and state assumptions."

            def approve_request(request: dict[str, Any]) -> bool:
                """Block until the user approves/rejects this DAG node (or time out)."""
                if approvals_q is None:
                    return True
                deadline = time.time() + 900
                while time.time() < deadline:
                    try:
                        node, approved = approvals_q.get(timeout=1)
                    except Exception:
                        continue
                    if str(node) in (str(request.get("node")), "*"):
                        return bool(approved)
                events_q.put({"type": "approval", "status": "timeout", **request})
                return False

            # Role team: the lead receives the command, emits a DAG, and flat workers
            # run its nodes (with approval gates when requested).
            outcome = run_team(
                tools, system, user, team=spec["team"], category=category,
                model=spec.get("model"), max_turns=max_turns,
                on_event=on_event, guidance=guidance, flag_pattern=pattern,
                persist=(spec.get("kind") == "custom"), diagnostic=diagnostic,
                approve=approve_request, ask_user=ask_user_callback,
            )
            result = outcome.result
            report = outcome.report
        else:
            result = solve(tools, system, user, on_event=on_event, guidance=guidance,
                           flag_pattern=pattern, persist=(spec.get("kind") == "custom"),
                           max_turns=max_turns, diagnostic=diagnostic)
        if known_flag is not None:
            status = "solved" if result.flag == known_flag else "failed"
        else:
            status = "solved" if result.flag else "done"  # custom: can't verify, just report
        events_q.put({"type": "status", "status": status, "flag": result.flag})
        # The team's reporter writes the review; otherwise synthesize a writeup so the
        # console can still show a human-readable 题解.
        if report:
            events_q.put({"type": "writeup", "text": report})
        elif status == "solved":
            writeup = generate_writeup(user, events_log, result.flag)
            if writeup:
                events_q.put({"type": "writeup", "text": writeup})
    except Exception as error:
        events_q.put({"type": "status", "status": "error",
                      "error": f"{type(error).__name__}: {error}"})
    finally:
        try:
            cleanup()
        except Exception:
            pass
        events_q.put({"type": "__done__"})
