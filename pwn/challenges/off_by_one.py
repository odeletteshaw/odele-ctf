"""Off-by-one: a copy loop iterates `<= len` and writes one byte past a 16-byte buffer,
clobbering the least-significant byte of the adjacent `authorized` int."""

from pwn.process import Process

DESCRIPTION = """A copy loop has an off-by-one:

    char buf[16];
    int  authorized = 0;         // 4 bytes, right after buf (little-endian)
    for (int i = 0; i <= len; i++)
        buf[i] = input[i];       // writes one byte too many: buf[16] hits authorized's LSB

Send input so the byte that lands on authorized's LSB is non-zero."""


class _OffByOne(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag

    def send(self, data: bytes) -> str:
        # buf[0:16], then authorized[16:20]. The off-by-one writes buf[16] = data[16].
        if len(data) >= 17 and data[16] != 0:
            return f"Welcome, admin.\n{self.flag}\n"
        return "Access denied.\n"


def make(flag: str) -> Process:
    return _OffByOne(flag)
