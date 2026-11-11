"""Protocol extraction: a libpcap capture of a TCP stream carrying an HTTP response with
chunked transfer-encoding. Reassemble the stream, parse the HTTP, and decode the chunks — the
flag is the response body."""

import base64
import struct

DESCRIPTION = (
    "A packet capture (libpcap) of an HTTP response using chunked transfer-encoding. The flag "
    "is the decoded response body. Reassemble the TCP stream, parse the HTTP, decode the chunks."
)

_SRC_IP = bytes([10, 0, 0, 2])
_DST_IP = bytes([10, 0, 0, 9])


def _frame(seq: int, payload: bytes) -> bytes:
    eth = b"\xde\xad\xbe\xef\x00\x01" + b"\xde\xad\xbe\xef\x00\x02" + b"\x08\x00"
    total = 20 + 20 + len(payload)
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, total, 0x1234, 0x4000, 64, 6, 0, _SRC_IP, _DST_IP)
    tcp = struct.pack(">HHIIHHHH", 4444, 80, seq, 0, (5 << 12) | 0x18, 65535, 0, 0)
    return eth + ip + tcp + payload


def _pcap(frames: list[bytes]) -> bytes:
    out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
    for i, frame in enumerate(frames):
        out += struct.pack("<IIII", i, 0, len(frame), len(frame)) + frame
    return out


def make(flag: str) -> str:
    data = flag.encode()
    third = -(-len(data) // 3)
    chunks = [data[i : i + third] for i in range(0, len(data), third)]
    body = b"".join(f"{len(c):x}\r\n".encode() + c + b"\r\n" for c in chunks) + b"0\r\n\r\n"
    resp = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n" + body
    )
    # split the response across a few in-order TCP segments
    size = -(-len(resp) // 4)
    segs = [resp[i : i + size] for i in range(0, len(resp), size)]
    base = 1000
    frames = [_frame(base + i * size, segs[i]) for i in range(len(segs))]
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(_pcap(frames)).decode()}"
