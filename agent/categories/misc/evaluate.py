"""Run the misc agent against local challenges. Add modules to CHALLENGES as you build
them (each exposing DESCRIPTION and make(flag) -> str). See CLAUDE.md 出题规范.

Usage: python agent/categories/misc/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent.evaluate import benchmark  # noqa: E402
from agent.categories.misc.agent import solve_misc, solve_misc_jail  # noqa: E402
from agent.categories.misc.challenges import brainfuck, compression_layers, morse, pyjail, xor_sequence  # noqa: E402

CHALLENGES = {
    "brainfuck": brainfuck,
    "compression_layers": compression_layers,
    "xor_sequence": xor_sequence,
    "morse": morse,
    "pyjail": pyjail,
}


def _make(module, flag):
    return module.make(flag)


def _solve(target, _description, on_event=None):
    if hasattr(target, "run"):  # jail challenge: an object with a run(code) method
        return solve_misc_jail(target, _description, on_event=on_event)
    return solve_misc(target, on_event=on_event)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
