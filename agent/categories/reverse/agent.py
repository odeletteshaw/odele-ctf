"""Reverse-engineering category. The agent attacks a COMPILED crackme binary through three
tools: disassemble (objdump the binary), run_binary (run it sandboxed, read output), and
run_python (compute: decode recovered bytes, invert a transform, build a keygen input).
The disassemble / run_binary tools live in agent/tools/bin.py.

The crackme is hermetic like every other category: it is our own tiny C program compiled at
make() time with the flag embedded, and it runs under the same no-network/rlimit sandbox as
run_python. The agent never sees the binary's path — only what the tools reveal.

Challenge interface: each module in reverse/challenges/ exposes DESCRIPTION and
make(flag) -> ReverseTarget (a compiled binary). See TODO.md.

Usage: python agent/categories/reverse/evaluate.py [name ...]
"""

import argparse
import importlib
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent.loop import SolveResult, Tool, solve  # noqa: E402
from agent.categories.reverse.target import ReverseTarget  # noqa: E402
from agent.tools.bin import disassemble_tool, run_binary_tool, strings_tool, triage_tool  # noqa: E402
from agent.tools.knowledge import knowledge_tool  # noqa: E402
from agent.tools.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are solving a reverse-engineering CTF challenge: a compiled binary (a
"crackme") that checks some input and, on success, reveals the flag. Your tools:
- triage: identify the binary in one pass (file type/arch from magic bytes, hashes, entropy,
  framework/packer fingerprints, a sample of strings). Run this FIRST to know what you have.
- strings: dump printable strings (min length 6) — the cheapest way to spot flag fragments,
  error messages, and format strings before disassembling.
- disassemble: dump the binary's arm64 instructions and every section's raw bytes
  (objdump -d -s). String literals and constant arrays (an encoded flag, a secret key) live
  in the __const / __cstring sections and appear in the hexdump as readable text or byte runs.
- run_binary: run the binary in a sandbox with optional stdin and argv; read its
  stdout/stderr/exit code.
- run_python: compute offline (no network) — decode bytes, invert a transform, or construct
  the exact input a check demands. z3-solver is available for symbolic/constraint solving:
  recover an input whose (possibly coupled, non-invertible-by-hand) transform matches a target.

Method (triage-first, top-down, hypothesis-driven):
- Run triage first to learn what the binary is, then strings for cheap wins, then disassemble
  to find main() and the check, then run_binary to confirm. Don't read the whole binary
  blindly — start from the goal (where the flag is printed) and work backward to the input.
- State a hypothesis ("this loop XORs the input against a key") and confirm it with ONE
  targeted check instead of reading everything.
- arm64 objdump notes: small immediates print in DECIMAL (mov w9, #170 means 170 = 0xaa);
  `eor w0, w8, w9` is XOR; `subs`/`cmp` + a conditional branch implements if/==. Constant data
  appears as a hexdump in the section contents — the hex column is the bytes, the right-hand
  column is their ASCII ('.' for non-printable).
- To reach the flag you may either reverse the check to produce a valid input and run_binary
  it, or recover the encoded flag + the transform from the disassembly and decode it in
  run_python. A keygen only needs ANY input that passes the check, not the original one.
- When a check couples many input bytes through a non-trivial transform (multiplication,
  shifts, XOR, cyclic mixing), don't brute-force or invert by hand — re-encode the transform
  as z3 bit-vector constraints in run_python and let the solver find the input.
- Back every conclusion with a coordinate (an address, a byte offset, a symbol) you actually
  saw in the tool output; if you haven't seen it, say so instead of guessing.

Flags look like flag{...}. Only report a flag you actually observed — printed by the binary or
decoded from its data. End your final message with the flag on its own line."""


def reverse_tools(target: ReverseTarget) -> list[Tool]:
    return [triage_tool(target.binary), strings_tool(target.binary),
            disassemble_tool(target.binary), run_binary_tool(target.binary), python_tool(),
            knowledge_tool("reverse")]


def solve_reverse(
    target: ReverseTarget,
    description: str,
    model: str | None = None,
    max_turns: int = 30,
    on_event=None,
) -> SolveResult:
    return solve(reverse_tools(target), SYSTEM_PROMPT, description, model=model,
                 max_turns=max_turns, on_event=on_event)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", help="challenge module name under reverse/challenges/")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    module = importlib.import_module(f"agent.categories.reverse.challenges.{args.challenge}")
    flag = f"flag{{{secrets.token_hex(12)}}}"
    target = module.make(flag)
    try:
        result = solve_reverse(target, module.DESCRIPTION, args.model)
    finally:
        target.cleanup()
    print(f"\nflag: {result.flag}  (real: {flag})  tool calls: {result.tool_calls}")


if __name__ == "__main__":
    main()
