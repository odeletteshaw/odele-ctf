"""ECB byte-at-a-time. The oracle returns AES-ECB-encrypt(your chosen plaintext || flag). Align
the flag to a block boundary, then recover it byte by byte by matching ciphertext blocks."""

import secrets

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

DESCRIPTION = (
    "An oracle encrypts (your chosen plaintext || flag) with AES-ECB under a fixed key and "
    "returns the ciphertext hex. Align the flag to a block boundary, then recover it one byte "
    "at a time by matching ciphertext blocks."
)


class _ECBOracle:
    def __init__(self, key: bytes, flag: bytes) -> None:
        self.key = key
        self.flag = flag

    def query(self, data: bytes) -> str:
        return AES.new(self.key, AES.MODE_ECB).encrypt(pad(data + self.flag, 16)).hex()


def make(flag: str):
    key = secrets.token_bytes(16)
    oracle = _ECBOracle(key, flag.encode())
    return (oracle, DESCRIPTION)
