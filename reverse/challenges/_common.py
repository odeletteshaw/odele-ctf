"""Shared helpers for reverse challenge authors. The agent never imports this: the tools it
gets are disassemble / run_binary / run_python, not these compile helpers (see agent.py)."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from reverse.target import ReverseTarget

CLANG = "clang"


def xor_c_array(data: bytes) -> str:
    """Render bytes as a C initializer list, e.g. '0xcc, 0xc6, 0xcb'."""
    return ", ".join(f"0x{b:02x}" for b in data)


def decode_loop(xor_key: int) -> str:
    """The C lines that XOR-decode the `enc` array and print it, plus a trailing newline."""
    return (
        f"    for (int i = 0; i < (int)sizeof(enc); i++) putchar(enc[i] ^ 0x{xor_key:02x});\n"
        "    putchar('\\n');\n"
    )


def compile_c(source: str) -> ReverseTarget:
    """Write C source into a fresh temp dir, compile with clang -O0, return the target."""
    workdir = Path(tempfile.mkdtemp(prefix="ctf-rev-"))
    src = workdir / "crackme.c"
    src.write_text(source)
    binary = workdir / "crackme"
    proc = subprocess.run(
        [CLANG, "-O0", "-o", str(binary), str(src)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(workdir, ignore_errors=True)
        raise RuntimeError(f"clang failed:\n{proc.stderr}")
    return ReverseTarget(binary=binary, workdir=workdir)
