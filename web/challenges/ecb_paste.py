"""ECB cut-and-paste. /ticket encrypts "email=<you>&role=user" with AES-ECB, one
independent block at a time. By choosing email lengths/contents, an attacker can (1)
make a block that encrypts to "admin"+padding and (2) align "role=" to a block edge so
the final block holds only the role value, then splice the captured admin block in.
email may not contain & or =, so parameter injection is not a shortcut.
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from ._harness import Request, start_server
import secrets

DESCRIPTION = (
    "A ticketing service. GET /ticket?email=X returns AES-ECB of 'email=X&role=user' "
    "(hex). GET /verify?cookie=<hex> decrypts and checks the role; admin gets the flag. "
    "email may not contain & or =."
)

HOME = (
    "<h1>Tickets</h1><p>/ticket?email=X encrypts <code>email=X&role=user</code> "
    "with AES-ECB (16-byte blocks). /verify?cookie=&lt;hex&gt; reads the role. "
    "email may not contain &amp; or =.</p>"
)


def start(flag: str) -> tuple[object, str]:
    key = secrets.token_bytes(16)

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/ticket" and req.method == "GET":
            email = req.query.get("email", "")
            if "&" in email or "=" in email:
                return 400, "email may not contain & or =", None
            profile = f"email={email}&role=user".encode("utf-8")
            # The weakness: ECB encrypts each block independently, so blocks are movable.
            ciphertext = AES.new(key, AES.MODE_ECB).encrypt(pad(profile, 16))
            return 200, ciphertext.hex(), {"Content-Type": "text/plain"}
        if req.route == "/verify" and req.method == "GET":
            try:
                ciphertext = bytes.fromhex(req.query.get("cookie", ""))
                plaintext = unpad(AES.new(key, AES.MODE_ECB).decrypt(ciphertext), 16)
            except Exception as error:
                return 400, f"bad cookie: {error}", None
            fields = dict(
                part.split(b"=", 1) for part in plaintext.split(b"&") if b"=" in part
            )
            if fields.get(b"role") == b"admin":
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden: role={fields.get(b'role')}", None
        return 404, "Not found", None

    return start_server(route)
