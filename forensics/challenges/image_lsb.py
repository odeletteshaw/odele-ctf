"""Image LSB stego: the flag is hidden in the least-significant bit of each pixel's red
channel (null-terminated). Read the pixels with Pillow and pull the LSBs."""

import base64
import io

from PIL import Image

DESCRIPTION = (
    "A PNG image hides a message in the least-significant bit of each pixel's red channel "
    "(row-major, null-terminated). Extract it."
)


def make(flag: str) -> str:
    bits = "".join(f"{b:08b}" for b in (flag.encode() + b"\x00"))
    w = 20
    h = 20
    img = Image.new("RGB", (w, h), (0x80, 0x80, 0x80))
    px = img.load()
    for i, ch in enumerate(bits):
        x, y = i % w, i // w
        r, g, b = px[x, y]
        px[x, y] = (0x80 | int(ch), g, b)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(buf.getvalue()).decode()}"
