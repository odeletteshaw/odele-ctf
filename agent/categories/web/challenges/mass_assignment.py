"""Mass assignment. Registration copies every field of the submitted JSON onto the
new user object, so a client can set fields the server never meant to expose — like
role=admin — and escalate privileges.
"""

import json
import secrets

from ._harness import Request, start_server

DESCRIPTION = (
    'A sign-up API. POST JSON {"username": ...} to /register, then GET /profile with '
    "header 'Authorization: Bearer <token>'. Admins see the flag."
)

HOME = (
    '<h1>Sign up</h1><p>POST JSON {"username": "..."} to /register to get a token, '
    "then GET /profile with Authorization: Bearer &lt;token&gt;.</p>"
)


def start(flag: str) -> tuple[object, str]:
    sessions: dict[str, dict] = {}

    def bearer(req: Request) -> str:
        auth = req.headers.get("Authorization", "") or ""
        return auth[len("Bearer ") :].strip() if auth.startswith("Bearer ") else ""

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/register" and req.method == "POST":
            try:
                data = json.loads(req.body or b"{}")
            except json.JSONDecodeError:
                return 400, "send a JSON body", None
            if not isinstance(data, dict) or "username" not in data:
                return 400, "username is required", None
            user = {"role": "user"}
            # The vulnerability: all client fields are merged, so role can be overridden.
            user.update(data)
            token = secrets.token_hex(8)
            sessions[token] = user
            return 200, f"registered. token: {token}", {"Content-Type": "text/plain"}
        if req.route == "/profile" and req.method == "GET":
            user = sessions.get(bearer(req))
            if user is None:
                return 401, "unknown token", None
            body = f"username={user['username']} role={user['role']}"
            if user.get("role") == "admin":
                body += f"\n{flag}"
            return 200, body, {"Content-Type": "text/plain"}
        return 404, "Not found", None

    return start_server(route)
