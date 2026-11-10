"""The reverse category's agent capabilities: disassemble a binary and run it sandboxed."""

import subprocess
from pathlib import Path

from core.agent import Tool
from core.sandbox import run_command

MAX_DISASM_CHARS = 60_000


def _disassemble(binary: Path) -> str:
    try:
        proc = subprocess.run(
            ["objdump", "-d", "-s", "--no-show-raw-insn", str(binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as error:
        return f"[could not disassemble: {error}]"
    out = proc.stdout
    if proc.stderr:
        out += ("\n" if out else "") + "[stderr]\n" + proc.stderr
    if len(out) > MAX_DISASM_CHARS:
        out = out[:MAX_DISASM_CHARS] + f"\n[truncated, {len(out)} chars]"
    return out


def disassemble_tool(binary: Path) -> Tool:
    return Tool(
        name="disassemble",
        description=(
            "Disassemble the target binary (objdump -d -s): arm64 instructions plus the raw "
            "bytes of every section. Read the program's logic and its data — string literals "
            "and constant arrays (an encoded flag, a secret key) live in __const / __cstring."
        ),
        parameters={"type": "object", "properties": {}},
        handler=lambda _args: _disassemble(binary),
    )


def run_binary_tool(binary: Path) -> Tool:
    def handler(args: dict) -> str:
        stdin = str(args.get("stdin", ""))
        argv = [str(x) for x in args.get("args", [])]
        return run_command([str(binary), *argv], stdin=stdin)

    return Tool(
        name="run_binary",
        description=(
            "Run the target binary in a sandbox (no network, time-limited) and return its "
            "stdout/stderr/exit code. Pass 'stdin' (text) and/or 'args' (command-line "
            "arguments). Use it to see what the program prints for a given input."
        ),
        parameters={
            "type": "object",
            "properties": {
                "stdin": {"type": "string", "description": "Text fed to standard input."},
                "args": {"type": "array", "items": {"type": "string"},
                         "description": "Command-line arguments."},
            },
        },
        handler=handler,
    )
