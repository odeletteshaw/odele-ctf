"""GraphQL with introspection left on. The public docs only mention `posts`, but an
introspection query reveals a hidden `flag` field that returns the secret. A tiny
hand-rolled resolver, so it is fully in-memory.
"""

import json

from ._harness import Request, start_server

DESCRIPTION = "A GraphQL API at /graphql. Public queries: { posts }."

HOME = (
    "<h1>GraphQL API</h1><p>POST JSON {\"query\": \"...\"} to /graphql. "
    "Try <code>{ posts }</code>.</p>"
)

SCHEMA = {
    "queryType": {"name": "Query"},
    "types": [
        {
            "name": "Query",
            "fields": [
                {"name": "posts", "type": {"name": "String"}},
                {"name": "flag", "type": {"name": "String"}},  # hidden from the docs
            ],
        }
    ],
}


def start(flag: str) -> tuple[object, str]:
    def route(req: Request):
        if req.route == "/" and req.method == "GET":
            return 200, HOME, None
        if req.route == "/graphql" and req.method == "POST":
            try:
                query = json.loads(req.body or b"{}").get("query", "")
            except json.JSONDecodeError:
                return 400, '{"errors":["invalid JSON"]}', {"Content-Type": "application/json"}
            # The flaw: introspection is enabled, exposing the hidden `flag` field.
            if "__schema" in query or "__type" in query:
                body = json.dumps({"data": {"__schema": SCHEMA}})
            elif "flag" in query:
                body = json.dumps({"data": {"flag": flag}})
            elif "posts" in query:
                body = json.dumps({"data": {"posts": "hello world"}})
            else:
                body = json.dumps({"errors": ["unknown field"]})
            return 200, body, {"Content-Type": "application/json"}
        return 404, "Not found", None

    return start_server(route)
