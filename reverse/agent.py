"""Reverse engineering category — NOT YET IMPLEMENTED.

Blocked on new agent tools. The agent needs to disassemble/decompile a binary
(objdump / radare2 / Ghidra headless) and ideally run symbolic execution (angr) to find
the input that produces the flag, plus a sandbox to run the binary. Once those exist,
implement solve_reverse() like web/crypto. See ROADMAP.md and TODO.md.
"""

SYSTEM_PROMPT = """You are solving a reverse-engineering CTF challenge.
You can disassemble/decompile the binary, run it, and run Python (angr available) to
reason about or symbolically execute it. Recover the algorithm or the input that the
program accepts, and extract the flag.
Flags look like flag{...}. End your final message with the flag on its own line."""

# TODO: build tools/disasm.py and/or a symbolic-execution tool, then
#       def solve_reverse(binary_path, description, ...) -> SolveResult.
