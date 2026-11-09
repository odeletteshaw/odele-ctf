"""Run the agent against local challenges and report which it solved.

A fresh random flag per run means a correct answer cannot be guessed or memorized.
Usage: python web/evaluate.py
"""

import secrets

from agent import solve_web
from challenges import sqli_login

CHALLENGES = {"sqli_login": sqli_login}


def main() -> None:
    solved = 0
    for name, challenge in CHALLENGES.items():
        flag = f"flag{{{secrets.token_hex(12)}}}"
        server, url = challenge.start(flag)
        try:
            result = solve_web(url, challenge.DESCRIPTION)
        finally:
            server.shutdown()
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} requests)")
    print(f"Solved {solved}/{len(CHALLENGES)}")


if __name__ == "__main__":
    main()
