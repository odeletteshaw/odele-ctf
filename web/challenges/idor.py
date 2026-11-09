"""IDOR. An order API returns any order by id with no authorization check, so a
low-privilege user can read another user's order. Pure in-memory data.
"""

import json

from ._harness import Request, start_server

DESCRIPTION = (
    "An order tracking API. You are signed in as 'bob' (user #2); your order is #1002. "
    "Check an order's status at /api/orders/<id>."
)

HOME = (
    "<h1>Order tracking</h1><p>Signed in as bob (user #2). "
    "Your latest order is #1002. Try /api/orders/1002</p>"
)


def start(flag: str) -> tuple[object, str]:
    orders = {
        1000: {"user": "admin", "item": "server rack", "note": flag},
        1001: {"user": "carol", "item": "keyboard", "note": "shipped"},
        1002: {"user": "bob", "item": "USB-C cable", "note": "delivered"},
        1003: {"user": "dave", "item": "monitor", "note": "processing"},
    }

    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route.startswith("/api/orders/"):
            raw = req.route.rsplit("/", 1)[-1]
            # The vulnerability: the order is returned without checking it is bob's.
            if raw.isdigit() and int(raw) in orders:
                body = json.dumps(orders[int(raw)])
                return 200, body, {"Content-Type": "application/json"}
            return 404, '{"error": "no such order"}', {"Content-Type": "application/json"}
        return 404, "Not found", None

    return start_server(route)
