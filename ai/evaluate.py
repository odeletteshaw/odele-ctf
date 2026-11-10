"""Run the AI red-team agent against the local Defender ladder. Unlike crypto/misc, the
target is itself an LLM, so each attempt is non-deterministic — this runs every challenge
several times (--runs) and reports a pass RATE, not a single PASS/FAIL.

Usage: python ai/evaluate.py [name ...] [--runs N]
"""

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.agent import solve_ai  # noqa: E402
from ai.challenges import both_filters, firm, input_filter, naive, output_filter  # noqa: E402

CHALLENGES: dict = {
    "naive": naive,
    "firm": firm,
    "output_filter": output_filter,
    "input_filter": input_filter,
    "both_filters": both_filters,
}


def run_once(module) -> tuple[bool, int]:
    flag = f"flag{{{secrets.token_hex(12)}}}"
    defender = module.make(flag)
    try:
        result = solve_ai(defender, module.DESCRIPTION)
    finally:
        defender.close()
    return result.flag == flag, result.tool_calls


def main(names: list[str], runs: int) -> None:
    selected = names or list(CHALLENGES)
    for name in selected:
        module = CHALLENGES[name]
        passes = 0
        calls_total = 0
        for _ in range(runs):
            ok, calls = run_once(module)
            passes += ok
            calls_total += calls
        avg = calls_total / runs if runs else 0
        print(f"{name:14s} {passes}/{runs} solved   (avg {avg:.1f} tool calls)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    main(args.names, args.runs)
