"""Hidden Number Problem: u_i = (t_i * x + e_i) mod q with small errors e_i (|e_i| < B).
Recover x (the flag as an integer) with LLL (fpylll)."""

import random
import secrets

from sympy import nextprime

DESCRIPTION = (
    "Hidden Number Problem: you are given many pairs (t_i, u_i) where u_i = (t_i * x + e_i) "
    "mod q, with the errors e_i small (|e_i| < B). x is the flag as an integer. Recover x "
    "with LLL (fpylll is available)."
)


def make(flag: str) -> str:
    q = nextprime(1 << 255)
    x = int.from_bytes(flag.encode(), "big")
    B = 1 << 120
    rng = random.Random(secrets.randbits(64))
    d = 40
    t = [rng.randrange(q) for _ in range(d)]
    e = [rng.randrange(-B, B) for _ in range(d)]
    u = [(t[i] * x + e[i]) % q for i in range(d)]
    pairs = "\n  ".join(f"({t[i]}, {u[i]})," for i in range(d))
    return f"{DESCRIPTION}\n\nq = {q}\nB = {B}\npairs (t_i, u_i):\n  {pairs}"
