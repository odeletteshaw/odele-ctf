"""CBC bit-flipping. The session cookie is AES-CBC ciphertext of a known plaintext
containing role=guest. Because CBC decryption XORs the previous ciphertext block into
the current plaintext block, flipping bytes in the previous block flips the chosen
plaintext bytes (garbling that previous block, which the server does not check).
guest and admin are both 5 bytes, so the flip is exact.
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from ._harness import Request, start_server
import secrets

# block0 is throwaway filler; block1 holds role=guest at a clean offset.
PLAINTEXT = b"a" * 16 + b"role=guest;data=x"

DESCRIPTION = (
    "A members panel. Your session cookie is AES-CBC encrypted, hex-encoded as "
    "IV + ciphertext, and decrypts to: 16 filler bytes then 'role=guest;data=x'. "
    "Send it back as ?cookie=<hex>. Only role=admin may read the flag."
)

HOME = (
    "<h1>Members panel</h1><p>Your cookie decrypts to "
    "<code>aaaaaaaaaaaaaaaarole=guest;data=x</code>. "
    "Call /panel?cookie=&lt;hex&gt;. Admins only.</p>"
)


def start(flag: str) -> tuple[object, str]:
    key = secrets.token_bytes(16)

    def issue() -> str:
        iv = secrets.token_bytes(16)
        ciphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(PLAINTEXT, 16))
        return (iv + ciphertext).hex()

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, {"Set-Cookie": f"cookie={issue()}; Path=/"}
        if req.route == "/cookie" and req.method == "GET":
            return 200, issue(), {"Content-Type": "text/plain"}
        if req.route == "/panel" and req.method == "GET":
            try:
                blob = bytes.fromhex(req.query.get("cookie", "") or req.cookies.get("cookie", ""))
                iv, ciphertext = blob[:16], blob[16:]
                plaintext = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext), 16)
            except Exception as error:
                return 400, f"bad cookie: {error}", None
            # The garbled filler block is ignored; only the role matters.
            if b"role=admin" in plaintext:
                return 200, f"Welcome, admin. {flag}", None
            return 403, "forbidden: you are not admin", None
        return 404, "Not found", None

    return start_server(route)
