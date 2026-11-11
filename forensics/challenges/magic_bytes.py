"""A file named 'photo.png' is actually a ZIP archive (its magic bytes are PK). Identify the
real type from the magic bytes — don't trust the extension — then extract the flag."""

import base64
import io
import zipfile

DESCRIPTION = "A file arrived named 'photo.png', but its extension is a lie. Identify its real type and find the flag."


def make(flag: str) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("flag.txt", flag)
    blob = buf.getvalue()
    return f"{DESCRIPTION}\n\nfile 'photo.png' (base64) = {base64.b64encode(blob).decode()}"
