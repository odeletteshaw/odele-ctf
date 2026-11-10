"""Pwn (binary exploitation) category — NOT YET IMPLEMENTED.

Blocked on a new agent tool. The agent needs to run the target binary in a sandbox and
interact over stdin/stdout (a `process_tool`), plus pwntools for crafting payloads.
Once that tool exists, implement solve_pwn() like web/crypto: give the agent the
process tool (+ run_python) and a prompt, hand it the binary, and have it pop a shell or
read the flag file. See ROADMAP.md and TODO.md.
"""

SYSTEM_PROMPT = """You are solving a binary exploitation (pwn) CTF challenge.
You can run the target binary and interact with it, and run Python (pwntools available)
to build payloads. Find the memory-corruption bug (overflow, format string, UAF, …),
craft an exploit, and use it to read the flag or spawn a shell.
Flags look like flag{...}. End your final message with the flag on its own line."""

# TODO: build tools/process.py (run + send/recv to a sandboxed binary), then
#       def solve_pwn(binary_path, description, ...) -> SolveResult.
