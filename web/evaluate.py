"""Run the agent against local challenges and report which it solved.

A fresh random flag per run means a correct answer cannot be guessed or memorized.
Usage: python web/evaluate.py [name ...]   (no names = run all)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from web.agent import solve_web  # noqa: E402
from web.challenges import (  # noqa: E402
    authbypass,
    cbc_flip,
    cmdi,
    ecb_paste,
    graphql,
    idor,
    jwt_auth,
    jwt_kid,
    jwt_weak,
    ldap_injection,
    lfi,
    mass_assignment,
    nosqli,
    pickle_deserialize,
    rate_limit_bypass,
    session_fixation,
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
    "cbc_flip": cbc_flip,
    "ecb_paste": ecb_paste,
    "lfi": lfi,
    "graphql": graphql,
    "ldap_injection": ldap_injection,
    "ssti": ssti,
    "jwt_auth": jwt_auth,
    "jwt_kid": jwt_kid,
    "jwt_weak": jwt_weak,
    "xxe": xxe,
    "nosqli": nosqli,
    "pickle_deserialize": pickle_deserialize,
    "rate_limit_bypass": rate_limit_bypass,
    "session_fixation": session_fixation,
    "mass_assignment": mass_assignment,
}


def _make(module, flag):
    return module.start(flag)  # (server, url)


def _solve(server_and_url, description):
    return solve_web(server_and_url[1], description)


def _cleanup(server_and_url):
    server_and_url[0].shutdown()


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve, cleanup=_cleanup)
