"""Hastad broadcast attack. The same message is sent to three recipients, all with
e=3. CRT combines the three ciphertexts into m^3 mod (n1 n2 n3); since m^3 is smaller,
the integer cube root recovers m.
"""

from Crypto.Util.number import bytes_to_long, getPrime

DESCRIPTION = "The same message was broadcast to three recipients, each using e=3."


def make(flag: str) -> str:
    e = 3
    m = bytes_to_long(flag.encode())
    lines = [DESCRIPTION, f"e = {e}"]
    for i in range(1, 4):
        n = getPrime(512) * getPrime(512)
        lines.append(f"n{i} = {n}")
        lines.append(f"c{i} = {pow(m, e, n)}")
    return "\n".join(lines)
