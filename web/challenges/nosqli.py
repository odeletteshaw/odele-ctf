"""NoSQL injection. A JSON login matches credentials against an in-memory store
Mongo-style. Because operator objects in the JSON are honored, a value like
{"$ne": ""} turns an equality check into "any non-empty", bypassing the password.
"""

import json
import secrets

from ._harness import Request, start_server

DESCRIPTION = (
    "A JSON login API. POST {\"user\": ..., \"pass\": ...} as JSON to /login. "
    "Only the admin account can see the flag."
)

HOME = (
    '<h1>Login API</h1><p>POST JSON {"user": "...", "pass": "..."} to /login '
    "(Content-Type: application/json).</p>"
)


def _matches(stored: dict, query: dict) -> bool:
    for key, condition in query.items():
        value = stored.get(key)
        if isinstance(condition, dict):
            # Operator object: this is what makes the injection work.
            for operator, operand in condition.items():
                if operator == "$ne" and not (value != operand):
                    return False
                if operator == "$gt" and not (value is not None and value > operand):
                    return False
                if operator == "$in" and value not in operand:
                    return False
                if operator not in ("$ne", "$gt", "$in"):
                    return False
        elif value != condition:
            return False
    return True


def start(flag: str) -> tuple[object, str]:
    # admin is first, so an injection that matches "any user" returns admin.
    users = [
        {"user": "admin", "pass": secrets.token_hex(16)},
        {"user": "bob", "pass": secrets.token_hex(16)},
    ]

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/login" and req.method == "POST":
            try:
                query = json.loads(req.body or b"{}")
            except json.JSONDecodeError:
                return 400, "send a JSON body", None
            if not isinstance(query, dict):
                return 400, "expected a JSON object", None
            # The vulnerability: the raw JSON (operators included) becomes the query.
            match = next((u for u in users if _matches(u, query)), None)
            if match is None:
                return 401, "no matching account", None
            if match["user"] == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 200, f"Welcome, {match['user']}.", None
        return 404, "Not found", None

    return start_server(route)
