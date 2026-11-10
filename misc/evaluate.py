"""Run the misc agent against local challenges. Add modules to CHALLENGES as you build
them (each exposing DESCRIPTION and make(flag) -> str). See TODO.md.

Usage: python misc/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from misc.agent import solve_misc  # noqa: E402
from misc.challenges import brainfuck, compression_layers, xor_sequence  # noqa: E402

CHALLENGES = {
    "brainfuck": brainfuck,
    "compression_layers": compression_layers,
    "xor_sequence": xor_sequence,
}


def _make(module, flag):
    return module.make(flag)


def _solve(text, _description):
    return solve_misc(text)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
