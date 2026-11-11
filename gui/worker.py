"""Subprocess entry point for one session. Runs the solve for a task spec and streams
structured events back to the parent over `events_q`; reads supervisor guidance from
`guidance_q`. Each session lives in its own process, so a crash or hang is contained.
"""

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import solve  # noqa: E402
from gui.builder import build_task  # noqa: E402


def worker_main(spec: dict[str, Any], events_q: Any, guidance_q: Any) -> None:
    def on_event(event: dict[str, Any]) -> None:
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
        pattern = re.compile(re.escape(prefix) + r"\{[^}\s]+\}")

    cleanup = lambda: None  # noqa: E731
    try:
        known_flag, tools, system, user, cleanup = build_task(spec)
        events_q.put({"type": "status", "status": "running"})
        # Custom (real external) targets get persist=True: the agent keeps going on text
        # without a flag instead of concluding early. The benchmark keeps default behavior.
        result = solve(tools, system, user, on_event=on_event, guidance=guidance,
                       flag_pattern=pattern, persist=(spec.get("kind") == "custom"))
        if known_flag is not None:
            status = "solved" if result.flag == known_flag else "failed"
        else:
            status = "solved" if result.flag else "done"  # custom: can't verify, just report
        events_q.put({"type": "status", "status": status, "flag": result.flag})
    except Exception as error:
        events_q.put({"type": "status", "status": "error",
                      "error": f"{type(error).__name__}: {error}"})
    finally:
        try:
            cleanup()
        except Exception:
            pass
        events_q.put({"type": "__done__"})
