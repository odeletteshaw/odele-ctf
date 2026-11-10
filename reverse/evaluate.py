"""Run the reverse agent against the local crackmes. Each module exposes DESCRIPTION and
make(flag) -> ReverseTarget (a compiled binary). See TODO.md.

Usage: python reverse/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from reverse.agent import solve_reverse  # noqa: E402
from reverse.challenges import crackme_serial, crackme_xor, run_me  # noqa: E402

CHALLENGES = {
    "run_me": run_me,
    "crackme_xor": crackme_xor,
    "crackme_serial": crackme_serial,
}


def _make(module, flag):
    return module.make(flag)


def _solve(target, description):
    return solve_reverse(target, description)


def _cleanup(target):
    target.cleanup()


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve, cleanup=_cleanup)
