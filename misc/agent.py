"""Misc category: grab-bag puzzles the agent solves with run_python. The tool already
exists, so this category is ready to fill with challenges — same shape as crypto:
each challenge exposes DESCRIPTION and make(flag) -> challenge text.

Usage: python misc/agent.py challenge.txt      (or pipe the challenge on stdin)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import SolveResult, solve  # noqa: E402
from core.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are solving a miscellaneous CTF challenge.
Your tool is run_python: write Python to work through the puzzle. There is no network.
These range over decoding, esoteric formats, programming puzzles, and clever tricks.
Read the challenge carefully, experiment, and compute the answer.
Flags look like flag{...}. Print the flag and end your final message with it on its own line."""


def solve_misc(challenge_text: str, model: str | None = None, max_turns: int = 30) -> SolveResult:
    return solve([python_tool()], SYSTEM_PROMPT, challenge_text, model=model, max_turns=max_turns)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", nargs="?")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    text = Path(args.challenge).read_text() if args.challenge else sys.stdin.read()
    result = solve_misc(text, args.model)
    print(f"\nflag: {result.flag}  tool calls: {result.tool_calls}")


if __name__ == "__main__":
    main()
