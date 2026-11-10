"""LDAP injection. The login builds a filter from unescaped user input, so a wildcard
(*) in the password turns the match into "any password", logging in as admin. The
directory and matching are simulated with fnmatch — no real LDAP server.
"""

import fnmatch

from ._harness import Request, start_server

DESCRIPTION = "A corporate portal backed by an LDAP directory."

FORM = """<h1>LDAP portal</h1>
<form method="post" action="/login">
  <input name="username"><input name="password" type="password">
  <button>Log in</button>
</form>"""


def start(flag: str) -> tuple[object, str]:
    # admin is first, so a match-anything filter authenticates as admin.
    directory = [
        {"uid": "admin", "password": "S3cr3t-" + flag[5:13]},
        {"uid": "guest", "password": "guest"},
    ]

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, FORM, None
        if req.route == "/login" and req.method == "POST":
            user = req.form.get("username", "")
            password = req.form.get("password", "")
            # The vulnerability: input is used as an LDAP filter pattern, wildcards and all.
            match = next(
                (e for e in directory
                 if fnmatch.fnmatch(e["uid"], user) and fnmatch.fnmatch(e["password"], password)),
                None,
            )
            if match is None:
                return 401, "authentication failed", None
            if match["uid"] == "admin":
                return 200, f"Welcome, admin. {flag}", None
            return 200, f"Welcome, {match['uid']}.", None
        return 404, "Not found", None

    return start_server(route)
