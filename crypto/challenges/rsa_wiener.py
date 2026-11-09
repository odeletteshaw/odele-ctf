"""RSA with a small private exponent d, vulnerable to Wiener's continued-fraction
attack. e is large (e = d^-1 mod phi); recovering d decrypts the flag.
"""

import math
import secrets

from Crypto.Util.number import bytes_to_long, getPrime, inverse

DESCRIPTION = "RSA where the private exponent was chosen small for speed."


def make(flag: str) -> str:
    p, q = getPrime(512), getPrime(512)
    n, phi = p * q, (p - 1) * (q - 1)
    # d ~120 bits is well under n^0.25/3, the Wiener bound for a 1024-bit modulus.
    while True:
        d = secrets.randbelow(2**120) | 1
        if math.gcd(d, phi) == 1:
            e = inverse(d, phi)
            break
    c = pow(bytes_to_long(flag.encode()), e, n)
    return f"{DESCRIPTION}\nn = {n}\ne = {e}\nc = {c}"
