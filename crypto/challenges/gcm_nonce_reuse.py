"""AES-GCM nonce reuse. Two messages were encrypted with the same nonce (and key), so they
share the same keystream. XOR the two ciphertexts with the known plaintext to recover the flag."""

import secrets

from Crypto.Cipher import AES

DESCRIPTION = (
    "Two messages were encrypted with AES-GCM using the SAME nonce and key. One message is "
    "known; the other is the flag. Same nonce means the same keystream was reused."
)

KNOWN = b"The quick brown fox jumps over the lazy dog."


def make(flag: str) -> str:
    key = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    c1, _ = AES.new(key, AES.MODE_GCM, nonce=nonce).encrypt_and_digest(KNOWN)
    c2, _ = AES.new(key, AES.MODE_GCM, nonce=nonce).encrypt_and_digest(flag.encode())
    return (
        f"{DESCRIPTION}\n"
        f"known plaintext: {KNOWN.decode()}\n"
        f"ciphertext1 (hex): {c1.hex()}\n"
        f"ciphertext2 (hex): {c2.hex()}"
    )
