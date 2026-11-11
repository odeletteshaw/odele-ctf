"""Shellcode injection (NX disabled): the program treats your input as executable code. Craft
a tiny shellcode that calls win(). The CPU is a toy — it only needs to model "call an address"."""

from pwn.process import Process

WIN_ADDR = 0x401176

DESCRIPTION = f"""The program reads your input into an EXECUTABLE buffer (no NX) and jumps to
it, executing it as code. The toy CPU supports one instruction:

    0x01 <addr: 8 bytes little-endian>    call the function at <addr>

win() (at {hex(WIN_ADDR)}) prints the flag. Craft shellcode that calls it."""


class _ShellcodeProcess(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag

    def send(self, data: bytes) -> str:
        i = 0
        while i < len(data):
            if data[i] == 0x01 and i + 8 < len(data):
                addr = int.from_bytes(data[i + 1 : i + 9], "little")
                if addr == WIN_ADDR:
                    return f"You win!\n{self.flag}\n"
                return f"called {hex(addr)}\n"
            i += 1
        return "no call\n"


def make(flag: str) -> Process:
    return _ShellcodeProcess(flag)
