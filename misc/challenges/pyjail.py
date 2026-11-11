"""A restricted Python 'jail': you send Python code and it runs, but any line containing a
banned word is rejected before execution. The flag is a variable named 'flag'. Escape the ban
(e.g. rebuild the name at runtime so the literal banned word never appears)."""

import contextlib
import io

DESCRIPTION = (
    "A restricted Python jail: send code, it runs, but any banned word in the code gets it "
    "rejected. The flag is in a variable named 'flag'. Escape the ban to print it."
)

BANNED = [
    "flag", "open", "import", "eval", "exec", "input", "globals", "vars", "dir", "getattr",
    "setattr", "delattr", "help", "breakpoint", "compile", "system", "os", "subprocess",
    "__", "read", "write",
]


class _Jail:
    def __init__(self, flag: str) -> None:
        self.ns = {"flag": flag}

    def run(self, code: str) -> str:
        low = code.lower()
        for word in BANNED:
            if word in low:
                return f"blocked: banned word '{word}'\n"
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(code, self.ns)
            return buf.getvalue() or "(no output)\n"
        except Exception as error:
            return f"error: {type(error).__name__}: {error}\n"


def make(flag: str):
    return _Jail(flag)
