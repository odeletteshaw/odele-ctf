"""Mersenne Twister (MT19937) state recovery. Given 624 consecutive 32-bit outputs, recover
the internal state (untemper), twist forward one step, and predict the next output — which is
used to XOR-decrypt the flag."""

import random
import secrets

DESCRIPTION = (
    "You have 624 consecutive 32-bit outputs of Python's Mersenne Twister (MT19937), as a "
    "hex string. Predict the next 32-bit output; the flag was XORed with those 4 bytes."
)


def make(flag: str) -> str:
    seed = secrets.randbits(64)
    rng = random.Random(seed)
    outputs = [rng.getrandbits(32) for _ in range(624)]
    next_out = rng.getrandbits(32)
    key = next_out.to_bytes(4, "big")
    ct = bytes(b ^ key[i % 4] for i, b in enumerate(flag.encode()))
    hex_out = "".join(f"{o:08x}" for o in outputs)
    return (
        f"{DESCRIPTION}\n"
        f"outputs (hex, 624 x 32-bit): {hex_out}\n"
        f"ciphertext (hex): {ct.hex()}"
    )
