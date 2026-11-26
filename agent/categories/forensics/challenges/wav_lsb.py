"""Audio stego: a WAV file whose flag is hidden in the least-significant bit of each 16-bit
PCM sample (MSB-first within each byte). The audio sounds like noise; the message is in the
low bits. The forensic skill: read the samples and pull LSBs. Pure stdlib (wave, struct)."""

import base64
import io
import struct
import wave

DESCRIPTION = "A WAV recording that sounds like static. Something is hidden in the samples."


def _bits(data: bytes):
    for byte in data:
        for i in range(7, -1, -1):  # MSB first
            yield (byte >> i) & 1


def make(flag: str) -> str:
    payload = flag.encode() + b"\x00"  # null terminator marks the end for the extractor
    bits = list(_bits(payload))
    # Keep the file small: run_python is stateless, so the agent re-pastes the embedded
    # base64 on every call — a big blob burns turns. A little carrier padding, not a lot.
    n_samples = max(len(bits), 400)
    samples = []
    for i in range(n_samples):
        carrier = 1000 + (i * 37 % 4000) - 2000  # deterministic pseudo-noise, fits int16
        bit = bits[i] if i < len(bits) else 0
        samples.append((carrier & ~1) | bit)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(8000)
        wf.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    blob = buf.getvalue()
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(blob).decode()}"
