"""AES-CBC padding oracle. Query the oracle with modified ciphertexts; it replies whether the
decrypted PKCS7 padding is valid. Recover the plaintext byte by byte."""

import secrets

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

DESCRIPTION = (
    "AES-CBC: a ciphertext encrypts pad(flag) under a secret key. You have a padding oracle — "
    "send it a ciphertext (iv || blocks, hex) and it replies 'valid'/'invalid' for the PKCS7 "
    "padding of the decrypted result. Recover the flag byte by byte (block size 16)."
)


class _PaddingOracle:
    def __init__(self, key: bytes) -> None:
        self.key = key

    def query(self, data: bytes) -> str:
        if len(data) < 32 or len(data) % 16 != 0:
            return "invalid"
        iv, ct = data[:16], data[16:]
        pt = AES.new(self.key, AES.MODE_CBC, iv).decrypt(ct)
        n = pt[-1]
        if 1 <= n <= 16 and pt[-n:] == bytes([n]) * n:
            return "valid"
        return "invalid"


def make(flag: str):
    key = secrets.token_bytes(16)
    iv = secrets.token_bytes(16)
    ct = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(flag.encode(), 16))
    oracle = _PaddingOracle(key)
    text = f"{DESCRIPTION}\n\niv (hex): {iv.hex()}\nciphertext (hex): {ct.hex()}"
    return (oracle, text)
