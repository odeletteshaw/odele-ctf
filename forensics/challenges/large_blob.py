"""Large-artifact carving: a ~1MB file with the flag (XOR-obfuscated) tucked after a magic
marker. Too big to embed as base64 in the prompt, so it is handed to the agent as a file in
its persistent workspace — read it from disk with run_python and carve the flag."""

import random

from forensics.workspace import Workspace

DESCRIPTION = (
    "A large binary file 'blob.bin' (~1MB) is in your working directory. A flag is hidden "
    "inside it, right after a magic marker. Read the file and carve the flag."
)

_MARKER = b"FLAGDATA"
_K = 0x5A
_OFFSET = 0x7A000


def make(flag: str):
    blob = bytearray(random.Random(0xC0FFEE).randbytes(1 << 20))
    payload = _MARKER + bytes(b ^ _K for b in flag.encode())
    blob[_OFFSET:_OFFSET + len(payload)] = payload
    return Workspace({"blob.bin": bytes(blob)})
