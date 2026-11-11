"""Vigenère cipher over bytes: c = (m + key[i % len]) mod 256 with a short lowercase key.
Recover the key from the known 'flag{' prefix, or brute-force the short keyspace."""

import secrets

DESCRIPTION = "A message was encrypted with the Vigenère cipher (byte-wise, mod 256). The key is short."


def make(flag: str) -> str:
    key = bytes(secrets.choice(range(97, 123)) for _ in range(4))  # 4 lowercase letters
    ct = bytes((c + key[i % len(key)]) % 256 for i, c in enumerate(flag.encode()))
    return f"{DESCRIPTION}\nkey length: {len(key)}\nciphertext (hex): {ct.hex()}"
