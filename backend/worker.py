"""Subprocess entry point for one session. Runs the solve for a task spec and streams
structured events back to the parent over `events_q`; reads supervisor guidance from
`guidance_q`. Each session lives in its own process, so a crash or hang is contained.
"""

import importlib
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.loop import generate_writeup, solve  # noqa: E402
from agent.taskbuilder import build_task  # noqa: E402
from agent.team import run_team  # noqa: E402


def worker_main(spec: dict[str, Any], events_q: Any, guidance_q: Any) -> None:
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
            # Role team: lead plans, recon collects, the direction expert solves, the
            # reporter writes the review (emitted as a writeup event).
            outcome = run_team(
                tools, system, user, team=spec["team"], category=category,
                model=spec.get("model"), max_turns=max_turns,
                on_event=on_event, guidance=guidance, flag_pattern=pattern,
                persist=(spec.get("kind") == "custom"), diagnostic=diagnostic,
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
        # After a solve, synthesize a writeup so the console can show a human-readable 题解.
        if status == "solved" and not report:
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
