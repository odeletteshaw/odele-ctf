"""RSA with e=3 and a short message, so c = m^3 exactly (m^3 < n). The integer cube
root of c recovers the flag — no factoring needed.
"""

from Crypto.Util.number import bytes_to_long, getPrime

DESCRIPTION = "RSA with public exponent e=3."


def make(flag: str) -> str:
    e = 3
    # 2048-bit modulus; the flag is only a few hundred bits, so m^3 stays below n.
    n = getPrime(1024) * getPrime(1024)
    m = bytes_to_long(flag.encode())
    c = pow(m, e, n)
    return f"{DESCRIPTION}\nn = {n}\ne = {e}\nc = {c}"
