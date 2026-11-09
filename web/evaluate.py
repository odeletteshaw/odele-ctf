"""Run the agent against local challenges and report which it solved.

A fresh random flag per run means a correct answer cannot be guessed or memorized.
Usage: python web/evaluate.py [name ...]   (no names = run all)
"""

import secrets
import sys

from agent import solve_web
from challenges import (
    authbypass,
    cmdi,
    idor,
    jwt_auth,
    mass_assignment,
    nosqli,
    sqli_login,
    ssrf,
    ssti,
    traversal,
    xxe,
)

CHALLENGES = {
    "sqli_login": sqli_login,
    "cmdi": cmdi,
    "traversal": traversal,
    "ssrf": ssrf,
    "idor": idor,
    "authbypass": authbypass,
    "ssti": ssti,
    "jwt_auth": jwt_auth,
    "xxe": xxe,
    "nosqli": nosqli,
    "mass_assignment": mass_assignment,
}


def main(names: list[str]) -> None:
    selected = names or list(CHALLENGES)
    solved = 0
    for name in selected:
        challenge = CHALLENGES[name]
        flag = f"flag{{{secrets.token_hex(12)}}}"
        server, url = challenge.start(flag)
        try:
            result = solve_web(url, challenge.DESCRIPTION)
        finally:
            server.shutdown()
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} requests)\n")
    print(f"Solved {solved}/{len(selected)}")


if __name__ == "__main__":
    main(sys.argv[1:])
