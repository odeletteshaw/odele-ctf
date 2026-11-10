"""Carving: a valid PNG with the flag appended after the IEND chunk. The image renders
fine, but the file is longer than the image — the flag lives in the bytes past IEND. The
forensic skill: don't trust the logical end-of-file; look at what's appended."""

import base64
import struct
import zlib

DESCRIPTION = "Someone sent this PNG. It opens fine — but the file seems bigger than it should be."


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(
        ">I", zlib.crc32(kind + data) & 0xFFFFFFFF
    )


def _tiny_png() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)  # 1x1, 8-bit grayscale
    idat = zlib.compress(b"\x00\x00")  # one scanline: filter byte + one pixel
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def make(flag: str) -> str:
    blob = _tiny_png() + flag.encode()  # flag glued on after IEND
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(blob).decode()}"
