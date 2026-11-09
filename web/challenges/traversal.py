"""Path traversal. A document viewer joins user input onto a web root without
checking for `..`. The filesystem is a VIRTUAL dict, so traversal reads only the
challenge's fake files — never anything real on the host.
"""

import posixpath

from ._harness import Request, start_server

DESCRIPTION = "A document viewer. Use ?file= to open a page under the web root."

WEB_ROOT = "/srv/www"


def start(flag: str) -> tuple[object, str]:
    # The flag lives at the filesystem root, one level above the served web root.
    files = {
        f"{WEB_ROOT}/index.html": "<h1>Docs</h1><p>Open a page with ?file=welcome.txt</p>",
        f"{WEB_ROOT}/welcome.txt": "Welcome. Served files live under /srv/www.",
        "/flag.txt": flag,
    }

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, files[f"{WEB_ROOT}/index.html"], None
        if req.route == "/view":
            name = req.query.get("file", "")
            # The vulnerability: no check that the result stays under WEB_ROOT.
            resolved = posixpath.normpath(posixpath.join(WEB_ROOT, name))
            if resolved in files:
                return 200, files[resolved], {"Content-Type": "text/plain"}
            return 404, f"{resolved}: not found", {"Content-Type": "text/plain"}
        return 404, "Not found", None

    return start_server(route)
