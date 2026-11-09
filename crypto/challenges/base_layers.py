"""Nested encodings: hex( base64( base32( flag ) ) ). Peel the layers to recover it."""

import base64

DESCRIPTION = "The flag was wrapped in several layers of encoding."


def make(flag: str) -> str:
    data = base64.b32encode(flag.encode())
    data = base64.b64encode(data)
    encoded = data.hex()
    return f"{DESCRIPTION}\nencoded: {encoded}"
