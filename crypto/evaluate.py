"""Run the crypto agent against local challenges and report which it solved.

A fresh random flag per run means a correct answer cannot be guessed or memorized.
Usage: python crypto/evaluate.py [name ...]   (no names = run all)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from crypto.agent import solve_crypto  # noqa: E402
from crypto.challenges import (  # noqa: E402
    aes_ctr_reuse,
    base_layers,
    dlp_pohlig,
    ecdsa_nonce_reuse,
    hash_crack,
    lcg_predict,
    rsa_common_factor,
    rsa_common_modulus,
    rsa_cube,
    rsa_fermat,
    rsa_hastad,
    rsa_wiener,
    xor_repeating,
    xor_single,
)

CHALLENGES = {
    "xor_single": xor_single,
    "xor_repeating": xor_repeating,
    "base_layers": base_layers,
    "rsa_cube": rsa_cube,
    "rsa_fermat": rsa_fermat,
    "rsa_wiener": rsa_wiener,
    "rsa_common_modulus": rsa_common_modulus,
    "rsa_hastad": rsa_hastad,
    "aes_ctr_reuse": aes_ctr_reuse,
    "ecdsa_nonce_reuse": ecdsa_nonce_reuse,
    "dlp_pohlig": dlp_pohlig,
    "rsa_common_factor": rsa_common_factor,
    "lcg_predict": lcg_predict,
    "hash_crack": hash_crack,
}


def _make(module, flag):
    return module.make(flag)


def _solve(text, _description):
    return solve_crypto(text)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
