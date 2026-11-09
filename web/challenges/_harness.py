"""Tiny localhost-only HTTP harness shared by the challenge servers.

Each challenge writes a route(req) -> (status, body, headers) function. Everything a
challenge needs is parsed onto the Request; nothing here touches the real filesystem,
shell, or network, so the vulnerabilities are simulated and cannot harm the host.
"""

import threading
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import parse_qs, urlparse


@dataclass
class Request:
    method: str
    path: str
    route: str
    query: dict[str, str]
    headers: object
    body: bytes
    form: dict[str, str]
    cookies: dict[str, str]


Route = Callable[[Request], tuple[int, object, dict[str, str] | None]]


def _first_values(raw: dict[str, list[str]]) -> dict[str, str]:
    return {k: v[0] for k, v in raw.items() if v}


def start_server(route: Route) -> tuple[HTTPServer, str]:
    """Serve `route` on a free localhost port and return (server, base_url)."""

    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            parsed = urlparse(self.path)
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            req = Request(
                method=self.command,
                path=self.path,
                route=parsed.path,
                query=_first_values(parse_qs(parsed.query)),
                headers=self.headers,
                body=body,
                form=_first_values(parse_qs(body.decode(errors="replace"))),
                cookies={k: m.value for k, m in cookie.items()},
            )
            try:
                status, payload, extra = route(req)
            except Exception as error:  # a challenge bug should not crash the agent run
                status, payload, extra = 500, f"server error: {error}", None
            data = payload if isinstance(payload, bytes) else str(payload).encode()
            self.send_response(status)
            extra = extra or {}
            self.send_header("Content-Type", extra.pop("Content-Type", "text/html"))
            self.send_header("Content-Length", str(len(data)))
            for key, value in extra.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = _dispatch

        def log_message(self, *args) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"
