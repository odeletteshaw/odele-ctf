"""Run the pwn agent against the local simulated targets. Each module exposes DESCRIPTION
and make(flag) -> Process. See TODO.md.

Usage: python agent/categories/pwn/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent.evaluate import benchmark  # noqa: E402
from agent.categories.pwn.agent import solve_pwn  # noqa: E402
from agent.categories.pwn.challenges import canary_bypass, format_leak, integer_overflow, off_by_one, overflow_auth, ret2win, shellcode, use_after_free  # noqa: E402

CHALLENGES = {
    "overflow_auth": overflow_auth,
    "ret2win": ret2win,
    "format_leak": format_leak,
    "integer_overflow": integer_overflow,
    "canary_bypass": canary_bypass,
    "shellcode": shellcode,
    "use_after_free": use_after_free,
    "off_by_one": off_by_one,
}


def _make(module, flag):
    return module.make(flag)


def _solve(proc, description, on_event=None):
    return solve_pwn(proc, description, on_event=on_event)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
