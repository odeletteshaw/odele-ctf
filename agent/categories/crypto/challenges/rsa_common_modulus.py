"""RSA common-modulus attack. The same message is encrypted under one modulus with
two coprime exponents. Bezout coefficients of e1, e2 recombine the ciphertexts into m.
"""

from Crypto.Util.number import bytes_to_long, getPrime

DESCRIPTION = "The same message was sent to one recipient under two public exponents."


def make(flag: str) -> str:
    n = getPrime(512) * getPrime(512)
    e1, e2 = 65537, 257  # coprime
    m = bytes_to_long(flag.encode())
    c1, c2 = pow(m, e1, n), pow(m, e2, n)
    return f"{DESCRIPTION}\nn = {n}\ne1 = {e1}\nc1 = {c1}\ne2 = {e2}\nc2 = {c2}"
