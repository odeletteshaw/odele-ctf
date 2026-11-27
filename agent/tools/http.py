"""The http_request agent capability, locked to a single target origin."""

import base64
import binascii
import copy
import hashlib
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
        "body": {"type": "string", "description": "Raw request body (sent as UTF-8 text). "
                 "For binary — a zip, image, or any bytes with values >127 — use body_b64 "
                 "instead, or the bytes get mangled."},
        "body_b64": {"type": "string", "description": "Request body as base64 of raw bytes, "
                     "sent verbatim (not UTF-8 re-encoded). Build the bytes in run_python "
                     "(e.g. a zip), base64-encode, and pass here. Overrides 'body'."},
        "files": {
            "type": "array",
            "description": "multipart/form-data file parts, for file-upload endpoints. "
                           "Each part's content is raw bytes via base64, so a crafted zip "
                           "(e.g. containing a symlink) uploads intact.",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "description": "Form field name (e.g. 'file')"},
                    "filename": {"type": "string", "description": "Uploaded file name"},
                    "content_b64": {"type": "string", "description": "File bytes as base64"},
                    "content_type": {"type": "string", "description": "Optional MIME type"},
                },
                "required": ["field", "content_b64"],
            },
        },
        "form": {"type": "object", "additionalProperties": {"type": "string"},
                 "description": "Extra multipart/form-data text fields to send alongside 'files'."},
    },
    "required": ["method", "path"],
}


class OutOfScope(ValueError):
    pass


def _decode_b64(value: Any, label: str) -> bytes:
    try:
        return base64.b64decode(str(value or ""), validate=False)
    except (binascii.Error, ValueError) as error:
        raise OutOfScope(f"{label} is not valid base64: {error}")


def _content_kwargs(args: dict[str, Any]) -> dict[str, Any]:
    """Resolve the request body into httpx kwargs, binary-safe.

    JSON tool arguments are text, so raw bytes (a zip whose symlink marker and CRC use
    high bytes) must arrive base64-encoded: a plain 'body' string is UTF-8-encoded by
    httpx and corrupts those bytes. Precedence: files (multipart) > body_b64 > body.
    """
    files = args.get("files")
    if files:
        if not isinstance(files, list):
            raise OutOfScope("'files' must be a list of {field, filename, content_b64}")
        parts = []
        for item in files:
            if not isinstance(item, dict):
                raise OutOfScope("each 'files' entry must be an object")
            field = str(item.get("field") or "file")
            filename = str(item.get("filename") or "upload.bin")
            content = _decode_b64(item.get("content_b64"), f"files[{field}].content_b64")
            ctype = str(item.get("content_type") or "application/octet-stream")
            parts.append((field, (filename, content, ctype)))
        form = args.get("form")
        return {"files": parts, "data": form if isinstance(form, dict) else None}
    if args.get("body_b64") is not None:
        return {"content": _decode_b64(args.get("body_b64"), "body_b64")}
    return {"content": args.get("body")}


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


def _body_fingerprint(args: dict[str, Any]) -> str:
    """A compact, body-type-agnostic digest so the repeat detector treats a changed
    binary upload as a new request (not an endless identical one)."""
    files = args.get("files")
    if files:
        return "files:" + hashlib.sha1(repr(files).encode("utf-8", "replace")).hexdigest()
    if args.get("body_b64") is not None:
        return "b64:" + hashlib.sha1(str(args.get("body_b64")).encode()).hexdigest()
    return "body:" + str(args.get("body") or "")


def _request_key(args: dict[str, Any]) -> list[Any]:
    """Repeat fingerprint: same verb/path/body is the same request, even if headers
    (a Cookie, a regenerated token) differ."""
    return [str(args.get("method", "GET")).upper(), str(args.get("path", "/")),
            _body_fingerprint(args)]


def _batch_key(args: dict[str, Any]) -> list[Any]:
    return [_request_key(r) for r in args.get("requests", []) if isinstance(r, dict)]


def run_http(target: str, client: httpx.Client, args: dict[str, Any]) -> str:
    try:
        url = build_url(target, args["path"])
        response = client.request(
            args["method"].upper(),
            url,
            headers=args.get("headers"),
            **_content_kwargs(args),
        )
    except (OutOfScope, httpx.HTTPError, httpx.InvalidURL, KeyError) as error:
        return f"Error: {error}"
    return format_response(response)


def http_tool(target: str, client: httpx.Client) -> Tool:
    return Tool(
        name="http_request",
        description=("Send an HTTP request to the challenge target. Redirects are returned, "
                     "not followed. For a binary body use body_b64; to upload a file "
                     "(multipart/form-data) use files — both carry raw bytes intact."),
        parameters=HTTP_PARAMETERS,
        handler=lambda args: run_http(target, client, args),
        repeat_key=_request_key,
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
            "Redirects are returned, not followed. For a binary body use body_b64; to upload "
            "a file (multipart/form-data) use files — both carry raw bytes intact."
        ),
        parameters=params,
        handler=handler,
        repeat_key=_request_key,
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
        repeat_key=lambda args: [str(args.get("target", 0)), str(args.get("path", "/"))],
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
                method, url, headers=req.get("headers"), **_content_kwargs(req)
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
        repeat_key=_batch_key,
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
        repeat_key=_batch_key,
    )


def new_http_client() -> httpx.Client:
    # Redirects are not followed, so a response cannot move a request off the target.
    # CTF targets routinely serve self-signed certificates; scope is enforced by the
    # origin lock, not by certificate trust, so don't let TLS verification block recon.
    return httpx.Client(
        follow_redirects=False, timeout=REQUEST_TIMEOUT_SECONDS, trust_env=False,
        verify=False,
    )
