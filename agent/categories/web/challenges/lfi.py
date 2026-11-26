"""Local file inclusion via a PHP-style wrapper. A page viewer "includes" files; a
normal include of the config executes it and hides the secret, but the php://filter
base64 wrapper reads the file's source instead, leaking the flag. Virtual filesystem,
so no real files are touched.
"""

import base64

from ._harness import Request, start_server

DESCRIPTION = "A PHP blog. Pages are PHP files included by /view?page=NAME (e.g. home, about)."

HOME = ("<h1>PHP Blog</h1><p>Pages are PHP files: /view?page=home (also: about). "
        "Includes run the file as PHP.</p>")


def start(flag: str) -> tuple[object, str]:
    # "Source" of each page. config holds the flag but is normally executed, not shown.
    sources = {
        "home": "<h1>Welcome</h1>",
        "about": "<h1>About us</h1>",
        "config": f"<?php $FLAG = '{flag}'; // keep this secret ?>",
    }
    rendered = {"home": "<h1>Welcome</h1>", "about": "<h1>About us</h1>", "config": ""}

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/view":
            page = req.query.get("page", "")
            # The vulnerability: the php://filter base64 wrapper returns raw source.
            # Lenient on the exact form (resource=config, config.php, string.* chains, …).
            if "php://filter" in page and "base64" in page:
                for name in sources:
                    if f"resource={name}" in page or name in page.split("resource=")[-1]:
                        return 200, base64.b64encode(sources[name].encode()).decode(), None
                return 404, "php://filter: unknown resource", None
            page = page.removesuffix(".php")
            if page in rendered:
                return 200, rendered[page], None
            return 404, f"no such page: {page}", None
        return 404, "Not found", None

    return start_server(route)
