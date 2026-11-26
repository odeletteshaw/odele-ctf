"""ECDSA with a reused nonce. Two signatures over secp256k1 share the same nonce k
(so they share r). From the two signing equations the nonce and then the private key
fall out by modular arithmetic; the private key is the flag.

The signatures are built straight from the ECDSA relation s = k^-1 (h + r*d) mod n, so
the recovery is exact without needing any elliptic-curve library.
"""

import secrets

from Crypto.Util.number import bytes_to_long, inverse

# secp256k1 group order.
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

DESCRIPTION = "Two ECDSA signatures (curve secp256k1) where the same nonce was reused."


def make(flag: str) -> str:
    d = bytes_to_long(flag.encode())  # the private key (< N for a ~240-bit flag)
    k = secrets.randbelow(N - 1) + 1
    r = secrets.randbelow(N - 1) + 1  # shared because k is shared
    h1, h2 = secrets.randbelow(N), secrets.randbelow(N)
    s1 = inverse(k, N) * (h1 + r * d) % N
    s2 = inverse(k, N) * (h2 + r * d) % N
    return (
        f"{DESCRIPTION}\nn = {N}\nr = {r}\n"
        f"s1 = {s1}\nh1 = {h1}\ns2 = {s2}\nh2 = {h2}\n"
        "The private key d, as bytes, is the flag."
    )
