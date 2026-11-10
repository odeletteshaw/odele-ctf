"""Run the pwn agent against the local simulated targets. Each module exposes DESCRIPTION
and make(flag) -> Process. See TODO.md.

Usage: python pwn/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from pwn.agent import solve_pwn  # noqa: E402
from pwn.challenges import format_leak, overflow_auth, ret2win  # noqa: E402

CHALLENGES = {
    "overflow_auth": overflow_auth,
    "ret2win": ret2win,
    "format_leak": format_leak,
}


def _make(module, flag):
    return module.make(flag)


def _solve(proc, description):
    return solve_pwn(proc, description)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
