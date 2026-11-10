"""Web category: the http_request tool and prompt. The model loop and provider
config live in core/ and are shared with every other category. The http_request tool
itself lives in tools/http.py.

Usage: python web/agent.py http://127.0.0.1:8000 "description of the challenge"
"""

import argparse
import sys
from pathlib import Path

import httpx

# Make the repo root importable whether run as a script or from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import SolveResult, Tool, solve  # noqa: E402
from tools.http import http_tool, new_http_client  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are an expert web penetration tester solving a CTF challenge.
You have two tools:
- http_request: reaches the challenge target and nothing else.
- run_python: runs Python offline (no network) for computation — encoding, hashing,
  HMAC, signing or forging tokens, brute-forcing a weak secret, breaking a cipher.
Use run_python to build any payload that needs real computation, then send it with
http_request. For example, recover a weak JWT secret by brute force, re-sign a token
with role=admin, then replay it.

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
- Mass assignment: send extra fields the server may bind blindly (role=admin,
  isAdmin=true) when creating or updating an object.
- NoSQL injection: in a JSON login, replace a value with an operator object such as
  {"$ne": ""} or {"$gt": ""} to turn an equality check into "match anything".
- XXE: if the app parses XML, declare an external entity
  (<!DOCTYPE d [<!ENTITY e SYSTEM "file:///flag.txt">]>) and reference &e; to read files.
- Template injection (SSTI): if reflected input is evaluated, {{7*7}} rendering as 49
  confirms it; then read exposed variables/config objects to reach a secret.
- Auth bypass: decode cookies/tokens (base64, JWT header.payload.signature); if they
  are unsigned or accept alg=none, forge a privileged role and replay the request.

Flags look like flag{...}. Only report a flag you actually saw in a response.
When you have it, end your final message with the flag on its own line."""


def web_tools(target: str, client: httpx.Client) -> list[Tool]:
    return [http_tool(target, client), python_tool()]


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
