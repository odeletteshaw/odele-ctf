"""Monoalphabetic substitution over lowercase letters, with a known-plaintext crib. A pangram
(containing every letter) is given in both plaintext and ciphertext, so the full substitution
is recoverable exactly, then applied to decrypt the flag."""

import random
import secrets

DESCRIPTION = (
    "A monoalphabetic substitution cipher (each letter maps to one fixed letter; non-letters "
    "unchanged). You have a known plaintext/ciphertext pair (a pangram) and the flag's "
    "ciphertext. Recover the substitution and decrypt the flag."
)

_PANGRAM = "the quick brown fox jumps over the lazy dog"
_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def make(flag: str) -> str:
    perm = list(_LETTERS)
    random.Random(secrets.randbits(64)).shuffle(perm)
    key = dict(zip(_LETTERS, perm))

    def enc(text: str) -> str:
        return "".join(key.get(c, c) for c in text)

    return (
        f"{DESCRIPTION}\n\n"
        f"known plaintext: {_PANGRAM}\n"
        f"known ciphertext: {enc(_PANGRAM)}\n"
        f"flag ciphertext: {enc(flag)}"
    )
