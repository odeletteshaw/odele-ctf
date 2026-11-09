"""Web category: the http_request tool and prompt. The model loop and provider
config live in core/ and are shared with every other category.

Usage: python web/agent.py http://127.0.0.1:8000 "description of the challenge"
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import httpx

# Make the repo root importable whether run as a script or from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import SolveResult, Tool, solve  # noqa: E402

MAX_RESPONSE_CHARS = 20_000
REQUEST_TIMEOUT_SECONDS = 15

SYSTEM_PROMPT = """You are an expert web penetration tester solving a CTF challenge.
Your only tool is http_request, which reaches the challenge target and nothing else.

Method:
- First map the app: fetch /, read the HTML, forms, links, comments, cookies, and
  response headers. Note every input (query params, form fields, path segments,
  headers, cookies) — each is a place to inject.
- Form a specific hypothesis about one vulnerability class, test the smallest payload
  that would confirm it, then escalate. Do not fire random payloads.
- Read every response as an oracle. Error messages, status codes, reflected input,
  resolved paths, and header/cookie changes tell you what the server did. Let each
  response narrow the next request. Never repeat an identical request.

Common vulnerability classes to consider:
- SQL injection: ' or " to provoke errors; ' OR '1'='1, comment with -- or #; note
  that the FIRST matching row may not be the admin — target the right account/column.
- Command injection: break out of a shell command with ; | & $(...) or backticks,
  then run cat/ls/env to read secrets.
- Path traversal: ../ to escape a web root; the server often echoes the resolved path
  on a miss — use it to calibrate how many ../ you need, or try an absolute path.
- SSRF: make the server fetch an internal URL; blocklists are often substring-based
  and miss internal hostnames or the cloud metadata IP (169.254.169.254).
- Broken access control / IDOR: change an id or enumerate ids to read other users'
  objects, even when the endpoint looks like it's "yours".
- Template injection (SSTI): if reflected input is evaluated, {{7*7}} rendering as 49
  confirms it; then read exposed variables/config objects to reach a secret.
- Auth bypass: decode cookies/tokens (base64, JWT header.payload.signature); if they
  are unsigned or accept alg=none, forge a privileged role and replay the request.

Flags look like flag{...}. Only report a flag you actually saw in a response.
When you have it, end your final message with the flag on its own line."""

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


def web_tools(target: str, client: httpx.Client) -> list[Tool]:
    return [
        Tool(
            name="http_request",
            description="Send an HTTP request to the challenge target. Redirects are returned, not followed.",
            parameters=HTTP_PARAMETERS,
            handler=lambda args: run_http(target, client, args),
        )
    ]


def new_http_client() -> httpx.Client:
    # Redirects are not followed, so a response cannot move a request off the target.
    return httpx.Client(
        follow_redirects=False, timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False
    )


def solve_web(
    target: str, description: str, model: str | None = None, max_turns: int = 30
) -> SolveResult:
    client = new_http_client()
    try:
        return solve(
            web_tools(target, client),
            SYSTEM_PROMPT,
            f"Target: {target}\n\nChallenge description: {description}",
            model=model,
            max_turns=max_turns,
        )
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Challenge base URL")
    parser.add_argument("description", help="Challenge description")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    result = solve_web(args.target, args.description, args.model)
    print(f"\nflag: {result.flag}  tool calls: {result.tool_calls}")


if __name__ == "__main__":
    main()
