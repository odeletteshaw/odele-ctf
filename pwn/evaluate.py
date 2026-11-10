"""Run the pwn agent against the local simulated targets. Each module exposes DESCRIPTION
and make(flag) -> Process. See TODO.md.

Usage: python pwn/evaluate.py [name ...]
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pwn.agent import solve_pwn  # noqa: E402
from pwn.challenges import format_leak, overflow_auth, ret2win  # noqa: E402

CHALLENGES: dict = {
    "overflow_auth": overflow_auth,
    "ret2win": ret2win,
    "format_leak": format_leak,
}


def main(names: list[str]) -> None:
    selected = names or list(CHALLENGES)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        module = CHALLENGES[name]
        result = solve_pwn(module.make(flag), module.DESCRIPTION)
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} tool calls)")
    print(f"\nSolved {solved}/{len(selected)}")


if __name__ == "__main__":
    main(sys.argv[1:])
