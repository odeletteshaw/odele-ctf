"""Generic PASS/FAIL benchmark loop shared by every category's evaluate.py.

Each category supplies thin make/solve/cleanup adapters that fit its own challenge
interface; the fresh-random-flag loop and reporting are identical everywhere. (ai is the
exception — its target is itself an LLM, so it uses its own multi-run harness.)

Set ODELE_EVAL_DIR (or pass transcript_dir) to save one JSONL transcript per challenge —
every agent message, tool call and tool result, then a final meta line. Those transcripts
are what failure analysis reads: judge the model on what it actually saw, not just on the
PASS/FAIL verdict.
"""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Callable

from agent.loop import EventFn, SolveResult


def benchmark(
    challenges: dict[str, Any],
    names: list[str],
    *,
    make: Callable[[Any, str], Any],
    solve: Callable[..., SolveResult],
    cleanup: Callable[[Any], None] | None = None,
    transcript_dir: str | Path | None = None,
) -> int:
    """Run each challenge once with a fresh random flag and report PASS/FAIL.

    make(module, flag) -> target; solve(target, description, on_event) -> SolveResult;
    cleanup(target) -> None. Returns the number of challenges solved."""
    save_dir = transcript_dir or os.environ.get("ODELE_EVAL_DIR")
    out_dir = Path(save_dir) if save_dir else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    selected = list(names) if names else list(challenges)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        started = time.time()
        target = make(challenges[name], flag)
        path = out_dir / f"{name}.jsonl" if out_dir is not None else None
        fh = path.open("w", encoding="utf-8") if path is not None else None

        def sink(event: dict[str, Any], _fh=fh) -> None:
            # Stream + flush so a long or stalled run is inspectable while it runs;
            # previously the transcript only appeared once the challenge finished.
            if _fh is not None:
                _fh.write(json.dumps(event, ensure_ascii=False) + "\n")
                _fh.flush()

        try:
            try:
                result = solve(target, challenges[name].DESCRIPTION, on_event=sink)
            finally:
                if cleanup:
                    cleanup(target)
            elapsed = time.time() - started
            passed = result.flag == flag
            solved += passed
            if fh is not None:
                meta = {"type": "meta", "name": name, "passed": passed, "flag": result.flag,
                        "tool_calls": result.tool_calls, "elapsed_s": round(elapsed, 2),
                        "final_text": result.final_text}
                sink(meta)
        finally:
            if fh is not None:
                fh.close()
        print(f"{'PASS' if passed else 'FAIL'} {name} "
              f"({result.tool_calls} tool calls, {elapsed:.1f}s)\n")
        if path is not None:
            print(f"transcript: {path}")
    print(f"Solved {solved}/{len(selected)}")
    return solved
