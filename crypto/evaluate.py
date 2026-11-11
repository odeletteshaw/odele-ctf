"""Run the crypto agent against local challenges and report which it solved.

A fresh random flag per run means a correct answer cannot be guessed or memorized.
Usage: python crypto/evaluate.py [name ...]   (no names = run all)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from crypto.agent import solve_crypto, solve_crypto_oracle  # noqa: E402
from crypto.challenges import (  # noqa: E402
    aes_ctr_reuse,
    affine,
    base_layers,
    dlp_pohlig,
    ecb_byte_at_a_time,
    ecdsa_nonce_reuse,
    gcm_nonce_reuse,
    hash_crack,
    hnp,
    lcg_predict,
    lattice_svp,
    lsb_oracle,
    mersenne_twister,
    padding_oracle,
    rsa_common_factor,
    rsa_common_modulus,
    rsa_cube,
    rsa_fermat,
    rsa_hastad,
    rsa_wiener,
    substitution,
    vigenere,
    xor_repeating,
    xor_single,
)

CHALLENGES = {
    "xor_single": xor_single,
    "xor_repeating": xor_repeating,
    "base_layers": base_layers,
    "affine": affine,
    "vigenere": vigenere,
    "substitution": substitution,
    "rsa_cube": rsa_cube,
    "rsa_fermat": rsa_fermat,
    "rsa_wiener": rsa_wiener,
    "rsa_common_modulus": rsa_common_modulus,
    "rsa_hastad": rsa_hastad,
    "aes_ctr_reuse": aes_ctr_reuse,
    "ecdsa_nonce_reuse": ecdsa_nonce_reuse,
    "gcm_nonce_reuse": gcm_nonce_reuse,
    "dlp_pohlig": dlp_pohlig,
    "rsa_common_factor": rsa_common_factor,
    "lcg_predict": lcg_predict,
    "mersenne_twister": mersenne_twister,
    "hash_crack": hash_crack,
    "padding_oracle": padding_oracle,
    "ecb_byte_at_a_time": ecb_byte_at_a_time,
    "lsb_oracle": lsb_oracle,
    "lattice_svp": lattice_svp,
    "hnp": hnp,
}


def _make(module, flag):
    return module.make(flag)


def _solve(target, _description):
    if isinstance(target, tuple):  # oracle challenge: (oracle, text)
        oracle, text = target
        return solve_crypto_oracle(oracle, text)
    return solve_crypto(target)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
