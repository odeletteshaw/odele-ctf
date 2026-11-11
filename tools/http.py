"""The http_request agent capability, locked to a single target origin."""

from typing import Any

import httpx

from core.agent import Tool

MAX_RESPONSE_CHARS = 20_000
REQUEST_TIMEOUT_SECONDS = 15

HTTP_PARAMETERS = {
    "type": "object",
    "properties": {
        "method": {"type": "string", "description": "GET, POST, etc."},
        "path": {"type": "string", "description": "Path and query, starting with /"},
        "headers": {"type": "object", "additionalProperties": {"type": "string"}},
        "body": {"type": "string", "description": "Raw request body"},
    },
    "required": ["method", "path"],
}


class OutOfScope(ValueError):
    pass


def build_url(target: str, path: str) -> httpx.URL:
    """Resolve path against target, refusing anything that leaves its origin."""
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise OutOfScope(f"path must be a single absolute path on the target: {path!r}")
    base = httpx.URL(target)
    url = httpx.URL(target.rstrip("/") + path)
    if (url.scheme, url.host, url.port) != (base.scheme, base.host, base.port):
        raise OutOfScope(f"{url} is outside {target}")
    return url


def format_response(response: httpx.Response) -> str:
    headers = "\n".join(f"{k}: {v}" for k, v in response.headers.items())
    body = response.text
    if len(body) > MAX_RESPONSE_CHARS:
        body = body[:MAX_RESPONSE_CHARS] + f"\n[truncated, {len(response.text)} chars total]"
    return f"HTTP {response.status_code}\n{headers}\n\n{body}"


def run_http(target: str, client: httpx.Client, args: dict[str, Any]) -> str:
    try:
        url = build_url(target, args["path"])
        response = client.request(
            args["method"].upper(),
            url,
            headers=args.get("headers"),
            content=args.get("body"),
        )
    except (OutOfScope, httpx.HTTPError, httpx.InvalidURL, KeyError) as error:
        return f"Error: {error}"
    return format_response(response)


def http_tool(target: str, client: httpx.Client) -> Tool:
    return Tool(
        name="http_request",
        description="Send an HTTP request to the challenge target. Redirects are returned, not followed.",
        parameters=HTTP_PARAMETERS,
        handler=lambda args: run_http(target, client, args),
    )


MAX_BATCH = 60
SNIPPET = 160


def http_batch_tool(target: str, client: httpx.Client) -> Tool:
    """A fuzzing-friendly batch variant of http_request: send many requests in one call and
    get one compact line per request (status + path + a short body snippet)."""

    def handler(args: dict[str, Any]) -> str:
        reqs = args.get("requests", [])
        if len(reqs) > MAX_BATCH:
            return f"Error: too many requests ({len(reqs)} > {MAX_BATCH}); split the batch."
        lines: list[str] = []
        for idx, req in enumerate(reqs):
            method = str(req.get("method", "GET")).upper()
            path = str(req.get("path", "/"))
            try:
                url = build_url(target, path)
                response = client.request(
                    method, url, headers=req.get("headers"), content=req.get("body")
                )
                snippet = " ".join(response.text.split())[:SNIPPET]
                lines.append(f"{idx}: {response.status_code} {method} {path} | {snippet}")
            except (OutOfScope, httpx.HTTPError, httpx.InvalidURL) as error:
                lines.append(f"{idx}: ERR {method} {path} {error}")
        return "\n".join(lines)

    return Tool(
        name="http_batch",
        description=(
            "Send up to 60 HTTP requests to the target in ONE call and get one compact line "
            "per request (index, status, path, and a short body snippet). Use it to fuzz or "
            "brute-force many candidate paths/params at once; then follow up on the hits with "
            "http_request for the full response."
        ),
        parameters={
            "type": "object",
            "properties": {
                "requests": {
                    "type": "array",
                    "items": HTTP_PARAMETERS,
                    "description": "List of requests to send.",
                }
            },
            "required": ["requests"],
        },
        handler=handler,
    )


def new_http_client() -> httpx.Client:
    # Redirects are not followed, so a response cannot move a request off the target.
    return httpx.Client(
        follow_redirects=False, timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False
    )
