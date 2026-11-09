"""SSRF. A link previewer fetches a user-supplied URL. Its blocklist only rejects
localhost/127.0.0.1, so internal hostnames slip through. "Fetching" is a lookup in a
VIRTUAL network map, so the server never makes a real outbound request.
"""

from ._harness import Request, start_server

DESCRIPTION = "A link previewer. Give it a URL and it fetches that page for you."

FORM = """<h1>Link previewer</h1>
<form method="post" action="/fetch">
  <input name="url" placeholder="https://...">
  <button>Preview</button>
</form>
<p>Note: internal services (e.g. http://internal/) are not meant to be public.</p>"""


def start(flag: str) -> tuple[object, str]:
    # The simulated network. Only these URLs "exist"; the flag sits on an internal host.
    # The internal index links onward so a reader has a trail to follow, not a dead end.
    network = {
        "http://example.com": "<title>Example Domain</title>",
        "http://internal": "<h1>Internal services</h1><ul><li><a href='/flag'>/flag</a></li></ul>",
        "http://internal/flag": flag,
        "http://169.254.169.254/latest/meta-data": "flag",
        "http://169.254.169.254/latest/meta-data/flag": flag,
    }

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, FORM, None
        if req.route == "/fetch" and req.method == "POST":
            url = req.form.get("url", "").strip().rstrip("/")
            # The weak defense: a substring blocklist that misses internal hosts.
            if "127.0.0.1" in url or "localhost" in url:
                return 403, "blocked: access to localhost is not allowed", None
            if url in network:
                return 200, f"<pre>{network[url]}</pre>", None
            return 502, f"could not resolve host: {url}", None
        return 404, "Not found", None

    return start_server(route)
