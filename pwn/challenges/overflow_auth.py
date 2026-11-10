"""Classic stack overflow into an adjacent variable: a 32-byte buffer sits right before an
`authorized` int. gets() has no bounds check, so writing more than 32 bytes spills into
`authorized`; making it non-zero unlocks the flag. Source is given, so the offset is
determinable — the task is understanding the layout and delivering the payload."""

from pwn.process import Process

DESCRIPTION = """The login checker (source below) never bounds-checks its input:

    char buf[32];
    int  authorized = 0;
    gets(buf);                 // reads your whole payload, no limit
    if (authorized != 0)
        print_flag();
    else
        puts("Access denied.");

`authorized` sits right after `buf` in memory. Send a payload that reaches it."""

_BUF = 32


class _AuthProcess(Process):
    def __init__(self, flag: str) -> None:
        self.flag = flag

    def send(self, data: bytes) -> str:
        # memory: buf[0:32] then authorized[32:36]. Overflow if the bytes landing on
        # authorized are non-zero.
        authorized = data[_BUF:_BUF + 4]
        if authorized and any(authorized):
            return f"Welcome, admin.\n{self.flag}\n"
        return "Access denied.\n"


def make(flag: str) -> Process:
    return _AuthProcess(flag)
