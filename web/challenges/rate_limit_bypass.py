"""Login rate limiting keyed on the client IP. The admin password is weak, so brute-force it —
but change the X-Forwarded-For header (or the source the limiter keys on) each attempt to stay
under the per-IP cap."""

import secrets

from ._harness import Request, start_server

DESCRIPTION = (
    "A login endpoint rate-limits: after 3 failed attempts per IP it returns 429. The admin "
    "password is weak. GET /login?username=admin&password=... — brute-force the password while "
    "changing the header the limiter keys on (X-Forwarded-For) to stay under the cap."
)

WEAK = ["secret", "password", "admin", "letmein", "123456", "qwerty"]

HOME = "<h1>Login</h1><p>GET /login?username=admin&password=... — 3 tries per IP, then 429.</p>"


def start(flag: str) -> tuple[object, str]:
    password = secrets.choice(WEAK)
    failures: dict[str, int] = {}

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "GET":
            ip = req.headers.get("X-Forwarded-For", "0.0.0.0")
            if failures.get(ip, 0) >= 3:
                return 429, "rate limited", None
            pw = req.query.get("password", "")
            if pw == password:
                return 200, f"Welcome, admin. {flag}", None
            failures[ip] = failures.get(ip, 0) + 1
            return 403, f"wrong password ({failures[ip]}/3)", None
        return 404, "Not found", None

    return start_server(route)
