"""ret2win: overflow past a 64-byte buffer and the 8-byte saved base pointer to overwrite the
saved return address with the address of win(), a function that prints the flag but is never
called. 64-bit, little-endian; the win address is given (no ASLR). The skill: compute the
padding (64 + 8) and pack the address with struct.pack('<Q', addr)."""

import struct

from pwn.process import Process

WIN_ADDR = 0x401176  # address of win(); given to the player (no ASLR)

DESCRIPTION = f"""A 64-bit program reads into a 64-byte buffer with no bounds check:

    void win()  {{ print_flag(); }}       // never called — but it's in the binary
    void vuln() {{ char buf[64]; read_all(buf); }}

Stack layout in vuln(): buf[64], then the saved base pointer (8 bytes), then the saved
return address (8 bytes). Overwrite the return address so the function "returns" into win().
win() is at {hex(WIN_ADDR)}. Remember: 64-bit addresses are packed little-endian."""

_PAD = 64 + 8  # buffer + saved rbp
_ADDR_SLOT = slice(_PAD, _PAD + 8)


class _Ret2WinProcess(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag

    def send(self, data: bytes) -> str:
        ret = data[_ADDR_SLOT]
        if len(ret) < 8:
            return "Segmentation fault (core dumped)\n"  # didn't reach the return address
        target = struct.unpack("<Q", ret)[0]
        if target == WIN_ADDR:
            return f"You win!\n{self.flag}\n"
        return f"Segmentation fault (core dumped)   [returned to {hex(target)}]\n"


def make(flag: str) -> Process:
    return _Ret2WinProcess(flag)
