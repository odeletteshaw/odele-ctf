"""Archive spelunking: a zip inside a zip inside a zip. The inner files are decoys; the
flag is in the ARCHIVE COMMENT of the innermost zip (a classic spot most tools skip).
The forensic skill: recurse through nested archives and check metadata, not just files."""

import base64
import io
import zipfile

DESCRIPTION = "A zip file. The files inside look like junk. Dig deeper."

_LAYERS = 3


def _wrap(payload: bytes, inner_name: str, comment: bytes = b"") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(inner_name, payload)
        zf.writestr("notes.txt", "nothing to see here\n")  # decoy
        if comment:
            zf.comment = comment
    return buf.getvalue()


def make(flag: str) -> str:
    # innermost zip carries the flag in its archive comment; a decoy file inside it.
    blob = _wrap(b"decoy payload, ignore me\n", "data.bin", comment=flag.encode())
    for i in range(_LAYERS - 1):
        blob = _wrap(blob, f"layer{_LAYERS - 1 - i}.zip")
    return f"{DESCRIPTION}\n\nfile (base64) = {base64.b64encode(blob).decode()}"
