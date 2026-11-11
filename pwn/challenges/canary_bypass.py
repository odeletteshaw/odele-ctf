"""Stack canary bypass: the program has a format-string leak AND a buffer overflow guarded by
a random 8-byte canary. First leak the canary with a %p format string, then send an overflow
payload that reproduces the canary and overwrites the saved return address with win()."""

import secrets
import struct

from pwn.process import Process

WIN_ADDR = 0x401176
_BUF = 32
_CANARY_SLOT = slice(_BUF, _BUF + 8)   # canary right after buf
_RET_SLOT = slice(_BUF + 16, _BUF + 24)  # buf[32] + canary[8] + rbp[8], then return address

DESCRIPTION = f"""A program reads your input twice. The FIRST read is passed to printf with no
format string of its own, and a single "%p" prints the 8-byte canary directly (labeled
"canary = 0x..."). The SECOND read gets()s into a 32-byte buffer:

    char buf[32];
    uint64_t canary = random();      // 8 bytes, unknown
    printf(input1);                  // "%p" -> leaks the canary (it's the only value printf reads)
    gets(buf);                       // overflow past buf into canary, rbp, ret
    if (canary != saved_canary) abort();
    return;                          // -> overwrite the return address with win()

win() is at {hex(WIN_ADDR)}. Stack layout: buf[32], canary[8], saved rbp[8], return address[8].
Reassemble the leaked canary little-endian (struct.pack('<Q', canary)) and pack win() the same way."""


class _CanaryProcess(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag
        self.canary = secrets.randbits(64)
        self._phase = "leak"

    def send(self, data: bytes) -> str:
        if self._phase == "leak":
            self._phase = "exploit"
            if b"%p" in data or b"%x" in data:
                return f"canary = {hex(self.canary)}\n"
            return "(no leak)\n"
        # exploit phase: buf(32) + canary(8) + rbp(8) + ret(8)
        if len(data) < _BUF + 24:
            return "*** stack smashing detected ***\n"
        if struct.unpack("<Q", data[_CANARY_SLOT])[0] != self.canary:
            return "*** stack smashing detected ***\n"
        target = struct.unpack("<Q", data[_RET_SLOT])[0]
        if target == WIN_ADDR:
            return f"You win!\n{self.flag}\n"
        return f"Segmentation fault (core dumped)   [returned to {hex(target)}]\n"


def make(flag: str) -> Process:
    return _CanaryProcess(flag)
