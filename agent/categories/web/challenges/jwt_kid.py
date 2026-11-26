"""JWT key confusion via the kid header. The verifier picks the signing key from the token's
own kid header. Point kid at a key you can sign with (the empty string key) and forge admin."""

import hashlib
import hmac
import json
import secrets

from ._common import b64u, bearer, ub64u
from ._harness import Request, start_server

DESCRIPTION = (
    "A JWT API. GET /login issues your token (kid=server). GET /admin needs an admin token. "
    "The verifier looks up the signing key by the token's own kid header."
)

HOME = (
    "<h1>JWT API</h1><p>Token at /login, then /admin with Authorization: Bearer "
    "&lt;token&gt;. The key is chosen by the token's kid header.</p>"
)


def _sign(payload: dict, kid: str, key: bytes) -> str:
    header = b64u(json.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}).encode())
    body = b64u(json.dumps(payload).encode())
    sig = hmac.new(key, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{b64u(sig)}"


def _verify(token: str, keys: dict) -> dict | None:
    try:
        header_b64, body_b64, signature_b64 = token.split(".")
        header = json.loads(ub64u(header_b64))
        key = keys.get(header.get("kid"), b"")
    except Exception:
        return None
    expected = hmac.new(key, f"{header_b64}.{body_b64}".encode(), hashlib.sha256).digest()
    if hmac.compare_digest(b64u(expected), signature_b64):
        return json.loads(ub64u(body_b64))
    return None


def start(flag: str) -> tuple[object, str]:
    server_key = secrets.token_bytes(32)
    keys = {"server": server_key, "admin": b""}  # kid=admin -> empty key

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "GET":
            token = _sign({"user": "bob", "role": "user"}, "server", server_key)
            return 200, f"your token:\n{token}", {"Content-Type": "text/plain"}
        if req.route == "/admin" and req.method == "GET":
            payload = _verify(bearer(req), keys)
            if payload is None:
                return 401, "invalid or missing token", None
            if payload.get("role") == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden: role '{payload.get('role')}' is not admin", None
        return 404, "Not found", None

    return start_server(route)
