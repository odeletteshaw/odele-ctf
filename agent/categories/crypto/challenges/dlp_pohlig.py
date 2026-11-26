"""Discrete logarithm over a prime whose group order p-1 is smooth, so Pohlig-Hellman
(plus baby-step giant-step on each small factor) recovers the exponent quickly. The
exponent is the flag.
"""

from secrets import SystemRandom

from Crypto.Util.number import bytes_to_long
from sympy import isprime, primerange

# Distinct primes below 1000: p-1 becomes squarefree with only tiny factors, so
# Pohlig-Hellman decomposes the log into trivially small baby-step/giant-step problems.
_POOL = list(primerange(3, 1000))
_rng = SystemRandom()

DESCRIPTION = (
    "Diffie-Hellman public value over a prime group whose order p-1 is smooth. "
    "Recover the exponent."
)


def _smooth_prime(min_bits: int) -> tuple[int, set[int]]:
    """Return (p, prime factors of p-1) where p-1 = 2 * product of distinct small primes."""
    while True:
        pool = _POOL.copy()
        _rng.shuffle(pool)
        m, factors = 2, {2}
        for q in pool:
            m *= q
            factors.add(q)
            if m.bit_length() >= min_bits:
                break
        if m.bit_length() >= min_bits and isprime(m + 1):
            return m + 1, factors


def _is_generator(g: int, p: int, factors: set[int]) -> bool:
    # g generates the whole group iff g^((p-1)/q) != 1 for every prime factor q of p-1.
    # We know the factorization (p-1 is smooth), so this is a handful of fast modpows —
    # much faster than sympy.primitive_root, which is very slow on large primes.
    return all(pow(g, (p - 1) // q, p) != 1 for q in factors)


def make(flag: str) -> str:
    x = bytes_to_long(flag.encode())
    g = 2
    while True:
        p, factors = _smooth_prime(x.bit_length() + 16)  # p > x, so the log is unique
        if _is_generator(g, p, factors):
            break
    h = pow(g, x, p)
    return f"{DESCRIPTION}\np = {p}\ng = {g}\nh = {h}\n(h = g^x mod p; x as bytes is the flag.)"
