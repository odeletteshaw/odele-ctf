"""Integer overflow in a size check: the length is stored in an 8-bit counter that wraps at
256. A 256+-byte input has a wrapped length that passes the `len < 16` check, but the full
input is still copied into a 16-byte buffer, overflowing into `authorized`."""

from pwn.process import Process

DESCRIPTION = """A service copies your input into a 16-byte buffer, but its size check uses an
8-bit length that wraps around:

    uint8_t len = strlen(input);    // wraps at 256
    char buf[16];
    int authorized = 0;
    if (len < 16)
        copy(buf, input);           // copies the full (256+-byte) input
    if (authorized) print_flag();

`authorized` sits right after `buf`. Send an input whose 8-bit length wraps below 16, yet is
long enough to overwrite `authorized`."""


class _IntOverflowProcess(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag

    def send(self, data: bytes) -> str:
        n = len(data) & 0xFF  # uint8_t wraps at 256
        if n >= 16:
            return "size too large\n"
        # The check passed (wrapped length < 16); the full input overflows buf[16] into
        # authorized (4 bytes right after the buffer).
        if len(data) >= 20 and any(data[16:20]):
            return f"Welcome, admin.\n{self.flag}\n"
        return "Access denied.\n"


def make(flag: str) -> Process:
    return _IntOverflowProcess(flag)
