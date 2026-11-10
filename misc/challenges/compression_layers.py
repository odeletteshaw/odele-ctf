"""The flag was compressed through several algorithms and base64-encoded. The agent
peels the layers (the magic bytes of each stage reveal which to use).
"""

import base64
import bz2
import lzma
import zlib

DESCRIPTION = "The flag was wrapped in several layers of compression, then base64-encoded."


def make(flag: str) -> str:
    data = zlib.compress(flag.encode())
    data = bz2.compress(data)
    data = lzma.compress(data)
    return f"{DESCRIPTION}\n\ndata (base64) = {base64.b64encode(data).decode()}"
