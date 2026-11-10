"""Network forensics: a libpcap capture of a few TCP segments whose payloads together spell
the flag. The segments are stored OUT OF ORDER in the capture, so concatenating them in
packet order gives garbage — you must reassemble by TCP sequence number. Pure stdlib struct
parsing (Ethernet + IPv4 + TCP, no options, no checksums needed)."""

import base64
import struct

DESCRIPTION = (
    "A packet capture (libpcap). The flag was sent over one TCP stream, but the packets "
    "didn't arrive in order."
)

_SRC_IP = bytes([10, 0, 0, 2])
_DST_IP = bytes([10, 0, 0, 9])


def _frame(seq: int, payload: bytes) -> bytes:
    eth = b"\xde\xad\xbe\xef\x00\x01" + b"\xde\xad\xbe\xef\x00\x02" + b"\x08\x00"
    total = 20 + 20 + len(payload)
    ip = struct.pack(
        ">BBHHHBBH4s4s", 0x45, 0, total, 0x1234, 0x4000, 64, 6, 0, _SRC_IP, _DST_IP
    )
    tcp = struct.pack(
        ">HHIIHHHH", 4444, 80, seq, 0, (5 << 12) | 0x18, 65535, 0, 0
    )
    return eth + ip + tcp + payload


def _pcap(frames: list[bytes]) -> bytes:
    # global header, little-endian (magic 0xa1b2c3d4 packed LE), link type 1 = Ethernet
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for i, frame in enumerate(frames):
        out += struct.pack("<IIII", i, 0, len(frame), len(frame)) + frame
    return out


def make(flag: str) -> str:
    data = flag.encode()
    size = max(1, -(-len(data) // 3))  # three chunks
    chunks = [data[i : i + size] for i in range(0, len(data), size)]
    base = 1000
    # (seq, payload) in correct order, then emitted shuffled so packet order != stream order
    segs = []
    off = 0
    for chunk in chunks:
        segs.append((base + off, chunk))
        off += len(chunk)
    order = [1, 2, 0] if len(segs) >= 3 else list(range(len(segs)))
    frames = [_frame(*segs[i]) for i in order]
    blob = _pcap(frames)
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(blob).decode()}"
