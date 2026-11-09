"""Repeating-key XOR. The known flag prefix 'flag{' leaks the start of the key."""

import secrets

DESCRIPTION = "Repeating-key XOR encryption; the plaintext is the flag."


def make(flag: str) -> str:
    key = secrets.token_bytes(secrets.choice([3, 4, 5]))
    plaintext = flag.encode()
    ciphertext = bytes(c ^ key[i % len(key)] for i, c in enumerate(plaintext))
    return (
        f"{DESCRIPTION}\nciphertext (hex): {ciphertext.hex()}\n"
        "Hint: the plaintext starts with 'flag{' and the key is at most 5 bytes."
    )
