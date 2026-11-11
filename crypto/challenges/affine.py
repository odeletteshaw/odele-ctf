"""Affine cipher over bytes: c = (a*m + b) mod 256 with a odd (so it is invertible). Recover
a and b from the known 'flag{' prefix, or brute-force the 128*256 (a,b) pairs."""

import secrets

DESCRIPTION = "A message was encrypted with an affine cipher: c = (a*m + b) mod 256."


def make(flag: str) -> str:
    a = secrets.choice(range(1, 256, 2))  # odd -> invertible mod 256
    b = secrets.randbelow(256)
    ct = bytes((a * c + b) % 256 for c in flag.encode())
    return f"{DESCRIPTION}\nciphertext (hex): {ct.hex()}"
