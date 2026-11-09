"""AES-CTR keystream reuse. Two messages were encrypted with the same key and nonce,
so they share a keystream. The first plaintext is known, which reveals the keystream
and thus the second plaintext (the flag).
"""

import secrets

from Crypto.Cipher import AES
from Crypto.Util import Counter

KNOWN = b"This is a routine public status update with nothing confidential in it."

DESCRIPTION = "Two messages were encrypted with AES-CTR under the same key and nonce."


def make(flag: str) -> str:
    key, nonce = secrets.token_bytes(16), secrets.token_bytes(8)

    def encrypt(plaintext: bytes) -> bytes:
        counter = Counter.new(64, prefix=nonce, initial_value=0)
        return AES.new(key, AES.MODE_CTR, counter=counter).encrypt(plaintext)

    c1 = encrypt(KNOWN)
    c2 = encrypt(flag.encode())
    return (
        f"{DESCRIPTION}\n"
        f"known first plaintext: {KNOWN.decode()}\n"
        f"ciphertext 1 (hex): {c1.hex()}\n"
        f"ciphertext 2 (hex): {c2.hex()}"
    )
