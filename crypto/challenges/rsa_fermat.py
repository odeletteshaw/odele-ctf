"""RSA whose two primes are close together, so Fermat's method factors n quickly.
Recover d and decrypt the flag.
"""

import secrets

from Crypto.Util.number import bytes_to_long, getPrime, inverse, isPrime

DESCRIPTION = "RSA with e=65537. The modulus looks ordinary but was generated carelessly."


def make(flag: str) -> str:
    e = 65537
    p = getPrime(512)
    # q sits just above p, so |p - q| is tiny and Fermat factorization converges fast.
    q = p + secrets.randbelow(2**20) * 2 + 2
    while not isPrime(q):
        q += 2
    n = p * q
    d = inverse(e, (p - 1) * (q - 1))  # noqa: F841 (kept to show the scheme is valid)
    c = pow(bytes_to_long(flag.encode()), e, n)
    return f"{DESCRIPTION}\nn = {n}\ne = {e}\nc = {c}"
