"""A polyglot: a valid PNG image that is ALSO a valid ZIP archive (the ZIP is appended after
the PNG's IEND, so image viewers stop early while unzip scans the end). The flag is in the ZIP."""

import base64
import io
import struct
import zipfile
import zlib

DESCRIPTION = (
    "A file that is both a valid PNG image and a valid ZIP archive. The image looks fine; "
    "the flag is stored on the ZIP side. Recognize the dual nature and extract it."
)


def _png() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    idat = zlib.compress(b"\x00")
    return (
        sig
        + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
        + struct.pack(">I", len(idat)) + b"IDAT" + idat + struct.pack(">I", zlib.crc32(b"IDAT" + idat) & 0xFFFFFFFF)
        + struct.pack(">I", 0) + b"IEND" + struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    )


def make(flag: str) -> str:
    z = io.BytesIO()
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("flag.txt", flag)
    blob = _png() + z.getvalue()
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(blob).decode()}"
