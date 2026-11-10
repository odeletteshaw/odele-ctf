"""Run the reverse agent against the local crackmes. Each module exposes DESCRIPTION and
make(flag) -> ReverseTarget (a compiled binary). See TODO.md.

Usage: python reverse/evaluate.py [name ...]
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reverse.agent import solve_reverse  # noqa: E402
from reverse.challenges import crackme_serial, crackme_xor, run_me  # noqa: E402

CHALLENGES: dict = {
    "run_me": run_me,
    "crackme_xor": crackme_xor,
    "crackme_serial": crackme_serial,
}


def main(names: list[str]) -> None:
    selected = names or list(CHALLENGES)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        target = CHALLENGES[name].make(flag)
        try:
            result = solve_reverse(target, CHALLENGES[name].DESCRIPTION)
        finally:
            target.cleanup()
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} tool calls)\n")
    print(f"Solved {solved}/{len(selected)}")


if __name__ == "__main__":
    main(sys.argv[1:])
