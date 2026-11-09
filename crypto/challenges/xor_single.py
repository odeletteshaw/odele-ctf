"""Single-byte XOR. The flag is XORed with one secret byte; brute-force all 256."""

import secrets

DESCRIPTION = "A message was encrypted with single-byte XOR."


def make(flag: str) -> str:
    key = secrets.randbelow(255) + 1
    ciphertext = bytes(b ^ key for b in flag.encode())
    return f"{DESCRIPTION}\nciphertext (hex): {ciphertext.hex()}"
