"""Authentication bypass. The session is an unsigned, client-side token: a
base64-encoded JSON blob the server trusts verbatim. Forging role=admin grants access.
"""

import base64
import json

from ._harness import Request, start_server

DESCRIPTION = "A members area. The flag at /flag is readable only by admins."

HOME = (
    "<h1>Members area</h1><p>Welcome, guest. Your session cookie holds your role. "
    "The flag is at /flag, for admins only.</p>"
)


def _encode(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    return raw.rstrip("=")  # drop padding so the value is cookie-clean


def _decode(value: str) -> dict:
    padded = value + "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def start(flag: str) -> tuple[object, str]:
    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            cookie = _encode({"user": "guest", "role": "guest"})
            return 200, HOME, {"Set-Cookie": f"session={cookie}; Path=/"}
        if req.route == "/flag" and req.method == "GET":
            try:
                session = _decode(req.cookies.get("session", ""))
            except Exception:
                return 400, "invalid session cookie", None
            # The vulnerability: the role is trusted from an unsigned client token.
            if session.get("role") == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden: admins only (your role: {session.get('role')})", None
        return 404, "Not found", None

    return start_server(route)
