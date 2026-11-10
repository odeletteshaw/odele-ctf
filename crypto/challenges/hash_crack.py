"""A weak, guessable password is the key. Its unsalted MD5 is given; brute-forcing it
from a common wordlist recovers the password, whose SHA-256 is the keystream that
decrypts the flag.
"""

import hashlib
import secrets

# A small set of common passwords; one is chosen per run and must be brute-forced back.
WEAK = ["sunshine", "iloveyou", "princess", "football", "monkey123", "dragon42",
        "letmein99", "trustno1", "superman", "baseball"]

DESCRIPTION = "A flag was encrypted under a key derived from a weak password."


def make(flag: str) -> str:
    password = secrets.choice(WEAK)
    digest = hashlib.md5(password.encode()).hexdigest()
    keystream = hashlib.sha256(password.encode()).digest()
    cipher = bytes(b ^ k for b, k in zip(flag.encode(), keystream))
    return (
        f"{DESCRIPTION}\nmd5(password) = {digest}\n"
        f"ciphertext (hex) = {cipher.hex()}\n"
        "(flag = ciphertext XOR sha256(password))"
    )
