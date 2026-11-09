"""Run the crypto agent against local challenges and report which it solved.

A fresh random flag per run means a correct answer cannot be guessed or memorized.
Usage: python crypto/evaluate.py [name ...]   (no names = run all)
"""

import secrets
import sys

from agent import solve_crypto
from challenges import base_layers, rsa_cube, rsa_fermat, xor_repeating, xor_single

CHALLENGES = {
    "xor_single": xor_single,
    "xor_repeating": xor_repeating,
    "base_layers": base_layers,
    "rsa_cube": rsa_cube,
    "rsa_fermat": rsa_fermat,
}


def main(names: list[str]) -> None:
    selected = names or list(CHALLENGES)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        text = CHALLENGES[name].make(flag)
        result = solve_crypto(text)
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} run_python calls)\n")
    print(f"Solved {solved}/{len(selected)}")


if __name__ == "__main__":
    main(sys.argv[1:])
