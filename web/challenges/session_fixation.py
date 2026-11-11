"""Predictable session tokens: the app issues tokens as base64 of the username with no
server-side randomness. Forge the admin's token and read the flag."""

import base64

from ._harness import Request, start_server

DESCRIPTION = (
    "The app issues session tokens as base64 of the username (no randomness). The admin is "
    "already logged in. Forge the admin's token and read /flag."
)

HOME = "<h1>App</h1><p>/login?user=X returns your token; /flag needs the admin token.</p>"


def _token(user: str) -> str:
    return base64.b64encode(user.encode()).decode()


def start(flag: str) -> tuple[object, str]:
    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "GET":
            user = req.query.get("user", "")
            return 200, f"your token:\n{_token(user)}", {"Content-Type": "text/plain"}
        if req.route == "/flag" and req.method == "GET":
            tok = req.cookies.get("token", "")
            if tok == _token("admin"):
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden (token decodes to {base64.b64decode(tok or '').decode(errors='replace')!r})", None
        return 404, "Not found", None

    return start_server(route)
