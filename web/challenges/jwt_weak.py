"""JWT with a weak signing secret. Unlike jwt_auth, the verifier is strict: it only
accepts HS256 with a valid signature (no alg=none bypass). The secret is a common
weak password, so the intended path is to brute-force it from the issued token, then
sign a fresh admin token. That requires real computation, not just HTTP.
"""

import base64
import hashlib
import hmac
import json
import secrets

from ._harness import Request, start_server

# A short list of common weak secrets; one is chosen per run. Brute force recovers it.
WEAK_SECRETS = ["secret", "password", "changeme", "letmein", "admin123", "qwerty", "jwt123"]

DESCRIPTION = (
    "A JWT-protected API with a weak signing secret. GET /login issues your token; "
    "GET /admin needs an admin token via 'Authorization: Bearer <token>'. Flag at /admin."
)

HOME = (
    "<h1>JWT API</h1><p>Token at /login, then /admin with Authorization: Bearer "
    "&lt;token&gt;. The signing key is rumored to be weak.</p>"
)


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _ub64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(payload: dict, secret: bytes) -> str:
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
    # Strict: only a correctly HS256-signed token is accepted.
    if header.get("alg") != "HS256":
        return None
    expected = hmac.new(secret, f"{header_b64}.{body_b64}".encode(), hashlib.sha256).digest()
    if hmac.compare_digest(_b64u(expected), signature_b64):
        return payload
    return None


def start(flag: str) -> tuple[object, str]:
    secret = secrets.choice(WEAK_SECRETS).encode()

    def bearer(req: Request) -> str:
        auth = req.headers.get("Authorization", "") or ""
        return auth[len("Bearer ") :].strip() if auth.startswith("Bearer ") else ""

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "GET":
            return 200, f"your token:\n{_sign({'user': 'bob', 'role': 'user'}, secret)}", {
                "Content-Type": "text/plain"
            }
        if req.route == "/admin" and req.method == "GET":
            payload = _verify(bearer(req), secret)
            if payload is None:
                return 401, "invalid or missing token", None
            if payload.get("role") == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden: role '{payload.get('role')}' is not admin", None
        return 404, "Not found", None

    return start_server(route)
