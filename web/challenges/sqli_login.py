"""Deliberately vulnerable login page (SQL injection). Binds to localhost only."""

import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

DESCRIPTION = "A small company portal. Only the administrator can see the flag."

LOGIN_PAGE = b"""<h1>Staff portal</h1>
<form method="post" action="/login">
  <input name="username"><input name="password" type="password">
  <button>Log in</button>
</form>"""


def start(flag: str) -> tuple[HTTPServer, str]:
    """Serve the challenge on a free local port and return (server, base_url)."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE users (username TEXT, password TEXT)")
    # guest comes first so that a bare ' OR 1=1 logs in as guest, not admin.
    db.execute("INSERT INTO users VALUES ('guest', ?)", (secrets.token_hex(16),))
    db.execute("INSERT INTO users VALUES ('admin', ?)", (secrets.token_hex(16),))

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            self.reply(200, LOGIN_PAGE) if self.path == "/" else self.reply(404, b"Not found")

        def do_POST(self) -> None:
            if self.path != "/login":
                return self.reply(404, b"Not found")
            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode(errors="replace"))
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
            # The vulnerability: user input is interpolated directly into SQL.
            query = (
                f"SELECT username FROM users "
                f"WHERE username = '{username}' AND password = '{password}'"
            )
            try:
                row = db.execute(query).fetchone()
            except sqlite3.Error as error:
                return self.reply(500, f"Database error: {error}".encode())
            if row is None:
                return self.reply(401, b"Invalid credentials")
            if row[0] == "admin":
                return self.reply(200, f"Welcome, admin. {flag}".encode())
            self.reply(200, f"Welcome, {row[0]}. Nothing here for you.".encode())

        def log_message(self, *args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"
