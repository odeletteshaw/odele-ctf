"""Generic PASS/FAIL benchmark loop shared by every category's evaluate.py.

Each category supplies thin make/solve/cleanup adapters that fit its own challenge
interface; the fresh-random-flag loop and reporting are identical everywhere. (ai is the
exception — its target is itself an LLM, so it uses its own multi-run harness.)
"""

import secrets
from typing import Any, Callable

from .agent import SolveResult


def benchmark(
    challenges: dict[str, Any],
    names: list[str],
    *,
    make: Callable[[Any, str], Any],
    solve: Callable[[Any, str], SolveResult],
    cleanup: Callable[[Any], None] | None = None,
) -> int:
    """Run each challenge once with a fresh random flag and report PASS/FAIL.

    make(module, flag) -> target; solve(target, description) -> SolveResult; and
    cleanup(target) -> None. Returns the number of challenges solved."""
    selected = list(names) if names else list(challenges)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        target = make(challenges[name], flag)
        try:
            result = solve(target, challenges[name].DESCRIPTION)
        finally:
            if cleanup:
                cleanup(target)
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} tool calls)\n")
    print(f"Solved {solved}/{len(selected)}")
    return solved
