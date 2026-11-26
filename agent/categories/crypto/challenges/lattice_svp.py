"""Lattice SVP: the flag is the shortest non-zero vector of a lattice, hidden behind a
unimodular scramble. Recover it with LLL (fpylll is available in run_python)."""

import random
import secrets

DESCRIPTION = (
    "A lattice basis matrix hides the flag as its shortest non-zero vector. Use LLL (the "
    "fpylll library is available) to find the short vector: its entries are 4-byte "
    "big-endian chunks of the flag (trailing zero padding)."
)


def _scramble(n: int, rng: random.Random) -> list[list[int]]:
    U = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    for _ in range(n * 4):
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        c = rng.randrange(-3, 4)
        for k in range(n):
            U[i][k] += c * U[j][k]
    return U


def make(flag: str) -> str:
    b = flag.encode() + b"\x00" * (-len(flag) % 4)
    d = len(b) // 4
    chunks = [int.from_bytes(b[i * 4 : (i + 1) * 4], "big") for i in range(d)]
    rng = random.Random(secrets.randbits(64))
    A = [[rng.randrange(1 << 64) for _ in range(d)] for _ in range(d)]
    B = [[A[i][j] if j < d else 0 for j in range(d + 1)] for i in range(d)]
    B.append([chunks[j] if j < d else 1 for j in range(d + 1)])
    U = _scramble(d + 1, rng)
    Bp = [
        [sum(U[i][k] * B[k][j] for k in range(d + 1)) for j in range(d + 1)]
        for i in range(d + 1)
    ]
    rows = ",\n  ".join("[" + ", ".join(str(x) for x in row) + "]" for row in Bp)
    return f"{DESCRIPTION}\n\nbasis (rows of a {d + 1}x{d + 1} matrix):\n[\n  {rows}\n]"
