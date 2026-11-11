"""Insecure deserialization: the app stores your session as a pickled dict in a cookie and
trusts it on /admin. Craft a pickle whose role is 'admin'."""

import base64
import pickle

from ._harness import Request, start_server

DESCRIPTION = (
    "The app stores your session in a 'session' cookie: base64 of a pickled dict "
    "{'user':'bob','role':'user'}. GET /login issues it; GET /admin needs role=admin. "
    "The server unpickles the cookie blindly."
)

HOME = "<h1>Pickle sessions</h1><p>/login issues your cookie; /admin reads it (role=admin gets the flag).</p>"


def start(flag: str) -> tuple[object, str]:
    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "GET":
            cookie = base64.b64encode(pickle.dumps({"user": "bob", "role": "user"})).decode()
            return 200, f"your session cookie:\n{cookie}", {"Content-Type": "text/plain"}
        if req.route == "/admin" and req.method == "GET":
            raw = req.cookies.get("session", "")
            try:
                obj = pickle.loads(base64.b64decode(raw))
                role = obj.get("role") if isinstance(obj, dict) else None
            except Exception as error:
                return 400, f"bad cookie: {error}", None
            if role == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 403, f"forbidden: role={role}", None
        return 404, "Not found", None

    return start_server(route)
