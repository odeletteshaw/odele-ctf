"""The http_request agent capability, locked to a single target origin."""

import copy
from pathlib import Path
from typing import Any

import httpx

from agent.loop import Tool

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


def _pick_target(targets: list[str], args: dict[str, Any]) -> str:
    """Resolve the 0-based 'target' argument to one of the allowed origins."""
    idx = args.get("target", 0)
    if isinstance(idx, bool) or not isinstance(idx, int) or not (0 <= idx < len(targets)):
        raise OutOfScope(f"target index {idx!r} out of range 0..{len(targets)-1}")
    return targets[idx]


def multi_http_tool(targets: list[str], client: httpx.Client) -> Tool:
    """http_request that can hit any of several listed targets (0-based 'target' arg)."""

    def handler(args: dict[str, Any]) -> str:
        try:
            target = _pick_target(targets, args)
        except OutOfScope as error:
            return f"Error: {error}"
        return run_http(target, client, args)

    params = copy.deepcopy(HTTP_PARAMETERS)
    params["properties"]["target"] = {
        "type": "integer",
        "description": "Which target to hit (0-based index into the target list in the prompt). Omit for the first target.",
    }
    return Tool(
        name="http_request",
        description=(
            "Send one HTTP request to a challenge target. 'target' selects which of the "
            "listed targets to hit (0-based index; see the target list in the prompt). "
            "Redirects are returned, not followed."
        ),
        parameters=params,
        handler=handler,
    )


def download_tool(targets: list[str], client: httpx.Client, workdir: Path | None) -> Tool:
    """Download a file from a target to the persistent workspace as raw bytes (no lossy
    text decoding), so run_python can then read binary files (zip archives, images, ...)."""

    def handler(args: dict[str, Any]) -> str:
        try:
            target = _pick_target(targets, args)
            url = build_url(target, args["path"])
            response = client.request("GET", url)
        except (OutOfScope, httpx.HTTPError, httpx.InvalidURL) as error:
            return f"Error: {error}"
        if workdir is None:
            return "Error: download_file needs a workspace (none was created for this target)"
        filename = str(args.get("filename") or "").strip()
        if not filename:
            filename = args["path"].rstrip("/").rsplit("/", 1)[-1] or "download.bin"
        safe = Path(filename).name  # basename only, so the agent can't escape the workspace
        if not safe:
            safe = "download.bin"
        try:
            dest = workdir / safe
            dest.write_bytes(response.content)
        except OSError as error:
            return f"Error saving file: {error}"
        ctype = response.headers.get("content-type", "?")
        return (
            f"Saved {len(response.content)} bytes to {safe!r} in the workspace "
            f"(Content-Type: {ctype}). Read it with run_python — e.g. "
            f"open({safe!r}, 'rb'), zipfile.ZipFile({safe!r}), etc."
        )

    return Tool(
        name="download_file",
        description=(
            "Download a file from a challenge target to the persistent workspace as RAW "
            "BYTES (not lossy text), so run_python can read binary files such as zip "
            "backups, images, or compiled binaries. 'path' is the file path on the target "
            "starting with '/'; 'target' selects which listed target (0-based, omit for the "
            "first); optional 'filename' overrides the saved name. Returns the saved name "
            "and size."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path on the target, starting with /"},
                "target": {"type": "integer", "description": "0-based target index; omit for the first"},
                "filename": {"type": "string", "description": "Optional name to save the file as (basename only)"},
            },
            "required": ["path"],
        },
        handler=handler,
    )


MAX_BATCH = 60
SNIPPET = 160


def _run_batch(target: str, client: httpx.Client, reqs: list) -> str:
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


def http_batch_tool(target: str, client: httpx.Client) -> Tool:
    """A fuzzing-friendly batch variant of http_request: send many requests in one call and
    get one compact line per request (status + path + a short body snippet)."""
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
        handler=lambda args: _run_batch(target, client, args.get("requests", [])),
    )


def multi_http_batch_tool(targets: list[str], client: httpx.Client) -> Tool:
    """http_batch variant that can target any of several listed origins."""

    def handler(args: dict[str, Any]) -> str:
        try:
            target = _pick_target(targets, args)
        except OutOfScope as error:
            return f"Error: {error}"
        return _run_batch(target, client, args.get("requests", []))

    return Tool(
        name="http_batch",
        description=(
            "Send up to 60 HTTP requests to one challenge target in ONE call and get one "
            "compact line per request (index, status, path, and a short body snippet). "
            "'target' selects which of the listed targets to hit (0-based). Use it to fuzz or "
            "brute-force many candidate paths/params at once; then follow up on hits with "
            "http_request for the full response."
        ),
        parameters={
            "type": "object",
            "properties": {
                "requests": {
                    "type": "array",
                    "items": HTTP_PARAMETERS,
                    "description": "List of requests to send.",
                },
                "target": {
                    "type": "integer",
                    "description": "Which target to hit (0-based index into the target list). Omit for the first target.",
                },
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
