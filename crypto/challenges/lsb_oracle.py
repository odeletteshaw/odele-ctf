"""RSA LSB oracle. The oracle reveals the low bit of m = c^d mod n for any queried ciphertext.
Batch-query c * 2^(i*e) mod n to read the binary digits of m/n, then reconstruct the flag."""

import secrets

from Crypto.Util.number import getPrime

DESCRIPTION = (
    "RSA: c = flag^e mod n. You have an LSB oracle — query it with a ciphertext and it replies "
    "'0'/'1' for the low bit of the decrypted plaintext. Recover the flag. (Ciphertexts are "
    "fixed-width big-endian, sized to n.)"
)


def make(flag: str):
    p = getPrime(128)
    q = getPrime(128)
    n = p * q
    e = 65537
    d = pow(e, -1, (p - 1) * (q - 1))
    m = int.from_bytes(flag.encode(), "big")
    c = pow(m, e, n)
    width = (n.bit_length() + 7) // 8

    class _Oracle:
        def query(self, data: bytes) -> str:
            c2 = int.from_bytes(data, "big")
            return str(pow(c2, d, n) & 1)

    oracle = _Oracle()
    text = f"{DESCRIPTION}\n\nn: {n}\ne: {e}\nc: {c}\nwidth: {width} bytes"
    return (oracle, text)
