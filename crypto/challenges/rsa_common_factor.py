"""Two RSA moduli share a prime factor. gcd(n1, n2) recovers it, which factors both;
then d = e^-1 mod phi decrypts the flag.
"""

from Crypto.Util.number import bytes_to_long, getPrime

DESCRIPTION = "Two RSA keys were generated carelessly and share a prime factor."


def make(flag: str) -> str:
    e = 65537
    p = getPrime(512)
    n1 = p * getPrime(512)
    n2 = p * getPrime(512)  # shares p with n1
    c = pow(bytes_to_long(flag.encode()), e, n1)
    return f"{DESCRIPTION}\nn1 = {n1}\nn2 = {n2}\ne = {e}\nc = {c}   # c is encrypted under n1"
