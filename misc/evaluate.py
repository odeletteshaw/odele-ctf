"""Run the misc agent against local challenges. Add modules to CHALLENGES as you build
them (each exposing DESCRIPTION and make(flag) -> str). See TODO.md.

Usage: python misc/evaluate.py [name ...]
"""

import secrets
import sys

from agent import solve_misc
from challenges import brainfuck, compression_layers, xor_sequence

CHALLENGES: dict = {
    "brainfuck": brainfuck,
    "compression_layers": compression_layers,
    "xor_sequence": xor_sequence,
}


def main(names: list[str]) -> None:
    if not CHALLENGES:
        print("no misc challenges yet — see misc/TODO.md")
        return
    selected = names or list(CHALLENGES)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        result = solve_misc(CHALLENGES[name].make(flag))
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} run_python calls)\n")
    print(f"Solved {solved}/{len(selected)}")


if __name__ == "__main__":
    main(sys.argv[1:])
