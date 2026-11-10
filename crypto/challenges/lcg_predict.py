"""A linear congruential generator with secret multiplier a and increment c (modulus m
is public). A few consecutive outputs leak enough to solve for a and c, after which the
generator is fully predictable; the flag is XORed with the following outputs.
"""

import secrets

from Crypto.Util.number import getPrime

DESCRIPTION = "A stream cipher keyed by an LCG. Only the modulus is public."


def make(flag: str) -> str:
    m = getPrime(64)
    a = secrets.randbelow(m - 2) + 2
    c = secrets.randbelow(m)
    state = secrets.randbelow(m)

    outputs = []
    for _ in range(6 + len(flag)):
        state = (a * state + c) % m
        outputs.append(state)

    leaked = outputs[:6]  # enough to recover a and c
    keystream = outputs[6:]  # one output per flag byte
    cipher = bytes(b ^ (k & 0xFF) for b, k in zip(flag.encode(), keystream))
    return (
        f"{DESCRIPTION}\nm = {m}\n"
        f"leaked outputs = {leaked}\n"
        f"ciphertext (hex) = {cipher.hex()}\n"
        "(each flag byte is XORed with (next LCG output & 0xff).)"
    )
