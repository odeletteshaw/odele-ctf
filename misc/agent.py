"""Misc category: grab-bag puzzles the agent solves with run_python. The tool already
exists, so this category is ready to fill with challenges — same shape as crypto:
each challenge exposes DESCRIPTION and make(flag) -> challenge text.

Usage: python misc/agent.py challenge.txt      (or pipe the challenge on stdin)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import SolveResult, Tool, solve  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are solving a miscellaneous CTF challenge.
Your tool is run_python: write Python to work through the puzzle. There is no network.
These range over decoding, esoteric formats, programming puzzles, and clever tricks.
Read the challenge carefully, experiment, and compute the answer.
Flags look like flag{...}. Print the flag and end your final message with it on its own line."""


def solve_misc(challenge_text: str, model: str | None = None, max_turns: int = 30) -> SolveResult:
    return solve([python_tool()], SYSTEM_PROMPT, challenge_text, model=model, max_turns=max_turns)


JAIL_SYSTEM_PROMPT = """You are escaping a restricted Python 'jail'. Your tools:
- send_code: send Python source to the jail; it runs it and returns the output, or a
  'blocked: banned word' message (the jail rejects code containing any banned word).
- run_python: compute offline (no network) — handy for building a payload as a string.

The jail holds the flag in a variable. Its code is checked for a BLACKLIST of words before
running. Escape the blacklist: rebuild a banned name at runtime so the literal word never
appears in your source (string concatenation, chr(), attribute lookups). Then print the flag.

Flags look like flag{...}. Print the flag and end your final message with it on its own line."""


def code_tool(jail) -> Tool:
    return Tool(
        name="send_code",
        description="Send Python source code to the restricted jail; returns its stdout, or a 'blocked'/'error' message.",
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python source to run in the jail"}},
            "required": ["code"],
        },
        handler=lambda args: jail.run(args.get("code", "")),
    )


def solve_misc_jail(jail, challenge_text: str, model: str | None = None,
                    max_turns: int = 30) -> SolveResult:
    return solve([code_tool(jail), python_tool()], JAIL_SYSTEM_PROMPT, challenge_text,
                 model=model, max_turns=max_turns)


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
