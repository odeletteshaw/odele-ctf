"""JWT forgery via the alg=none bypass. /login issues a properly HS256-signed token
for a normal user. The verifier, however, trusts the token's own alg header: a token
with alg=none is accepted without any signature. Forging {"role":"admin","alg":"none"}
grants admin. The server's signing secret is random and never exposed.
"""

import base64
import hashlib
import hmac
import json
import secrets

from ._harness import Request, start_server

DESCRIPTION = (
    "A JWT-protected API. GET /login issues your token; GET /admin needs an admin token "
    "(send it as 'Authorization: Bearer <token>'). The flag is at /admin."
)

HOME = (
    "<h1>JWT API</h1><p>Get a token at /login, then call /admin with "
    "Authorization: Bearer &lt;token&gt;. Only admins may read the flag.</p>"
)


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _ub64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign_hs256(payload: dict, secret: bytes) -> str:
    header = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64u(json.dumps(payload).encode())
    signature = hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64u(signature)}"


def _verify(token: str, secret: bytes) -> dict | None:
    try:
        header_b64, body_b64, signature_b64 = token.split(".")
        header = json.loads(_ub64u(header_b64))
        payload = json.loads(_ub64u(body_b64))
    except Exception:
        return None
    alg = header.get("alg")
    # The vulnerability: the alg is read from the untrusted token. alg=none skips
    # verification entirely.
    if alg == "none":
        return payload
    if alg == "HS256":
        expected = hmac.new(secret, f"{header_b64}.{body_b64}".encode(), hashlib.sha256).digest()
        if hmac.compare_digest(_b64u(expected), signature_b64):
            return payload
    return None


def start(flag: str) -> tuple[object, str]:
    secret = secrets.token_bytes(32)  # random per run, never sent to the client

    def bearer(req: Request) -> str:
        auth = req.headers.get("Authorization", "") or ""
        if auth.startswith("Bearer "):
            return auth[len("Bearer ") :].strip()
        return req.cookies.get("token", "")

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "GET":
            token = _sign_hs256({"user": "bob", "role": "user"}, secret)
            return 200, f"your token:\n{token}", {"Content-Type": "text/plain"}
        if req.route == "/admin" and req.method == "GET":
            payload = _verify(bearer(req), secret)
            if payload is None:
                return 401, "invalid or missing token", None
            if payload.get("role") == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden: role '{payload.get('role')}' is not admin", None
        return 404, "Not found", None

    return start_server(route)
