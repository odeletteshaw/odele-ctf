"""A Brainfuck program that prints the flag. The agent writes a BF interpreter in
run_python and executes it to recover the output.
"""

DESCRIPTION = "This Brainfuck program prints the flag when run."


def _to_bf(text: str) -> str:
    out, prev = [], 0
    for ch in text:
        delta = ord(ch) - prev
        out.append(("+" if delta >= 0 else "-") * abs(delta))
        out.append(".")
        prev = ord(ch)
    return "".join(out)


def make(flag: str) -> str:
    return f"{DESCRIPTION}\n\n{_to_bf(flag)}"
