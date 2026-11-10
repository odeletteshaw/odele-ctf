"""The flag is XORed with a keystream defined by a stated formula. The agent reproduces
the keystream and XORs it back — a follow-the-spec programming puzzle.
"""

DESCRIPTION = "The flag was XORed byte-by-byte with a keystream k[i] = (7*i*i*i + 13) mod 256."


def _keystream(n: int) -> list[int]:
    return [(7 * i * i * i + 13) % 256 for i in range(n)]


def make(flag: str) -> str:
    cipher = bytes(b ^ k for b, k in zip(flag.encode(), _keystream(len(flag))))
    return f"{DESCRIPTION}\nciphertext (hex) = {cipher.hex()}"
