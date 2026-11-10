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


def new_http_client() -> httpx.Client:
    # Redirects are not followed, so a response cannot move a request off the target.
    return httpx.Client(
        follow_redirects=False, timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False
    )
