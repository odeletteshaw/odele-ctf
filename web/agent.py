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
from tools.http import (  # noqa: E402
    download_tool,
    http_batch_tool,
    http_tool,
    multi_http_batch_tool,
    multi_http_tool,
    new_http_client,
)
from tools.phar import phar_tool  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are an expert web penetration tester solving a CTF challenge.
You have four tools:
- http_request: send ONE HTTP request to the challenge target and read the full response.
- http_batch: send up to 60 HTTP requests in one call (one compact line each) to fuzz or
  brute-force many candidate paths/params at once; follow up on hits with http_request.
- download_file: download a file from the target to a persistent workspace as RAW BYTES.
  Use this for binary files (zip backups, images, ...) — http_request returns text and would
  mangle them. Then read the saved file with run_python.
- run_python: runs Python offline (no network) for computation — encoding, hashing,
  HMAC, signing or forging tokens, brute-forcing a weak secret, breaking a cipher. It runs
  in the SAME persistent workspace download_file writes into, so it can read those files
  (os.listdir('.'), open('name','rb'), zipfile.ZipFile('name'), ...).
Use run_python to build any payload that needs real computation, then send it with
http_request. For example, recover a weak JWT secret by brute force, re-sign a token
with role=admin, then replay it. When you find a backup file (www.zip, .bak, .git, ...),
download it with download_file and read its source with run_python instead of trying to
read the binary through http_request's lossy text.

Method:
- First map the app: fetch /, read the HTML, forms, links, comments, cookies, and
  response headers. Note every input (query params, form fields, path segments,
  headers, cookies) — each is a place to inject.
- Form a specific hypothesis about one vulnerability class, test the smallest payload
  that would confirm it, then escalate. Do not fire random payloads.
- Read every response as an oracle. Error messages, status codes, reflected input,
  resolved paths, and header/cookie changes tell you what the server did. Let each
  response narrow the next request. Never repeat an identical request.
- Don't conclude or give up until you actually have the flag. When a technique stalls,
  switch to a genuinely different attack class instead of retrying near-variations of the
  same failed one — there is usually more than one way in, so keep forming new hypotheses.

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
- Block-cipher modes: AES-ECB encrypts each 16-byte block independently, so blocks are
  interchangeable. ECB cut-and-paste: (1) craft an input so a chosen value (e.g. "admin")
  sits ALONE in one block followed by a full block of PKCS7 padding — you can embed the
  padding bytes in your input (percent-encode them, e.g. 0x0b), they needn't be printable;
  (2) craft a second input so the field name ends exactly at a block boundary (e.g. "&role="
  as the last bytes of a block); (3) splice block-2 then block-1. CBC bit-flip: flip a bit in
  the IV or previous ciphertext block to flip that same plaintext bit. Padding oracle: a
  server that reports valid/invalid padding leaks plaintext byte by byte.
- PHP deserialization: a value passed straight into unserialize() (or into file operations
  with a phar:// path) triggers object injection — craft O:len:"Class":N:{...}. A PRIVATE
  property $prop of class C is serialized as \\0C\\0prop, and PROTECTED as \\0*\\0prop — the
  \\0 is a raw null byte, written as %00 in a URL; the s:N: length counts the RAW bytes
  (e.g. "\\0Name\\0username" is 14 bytes: 1+4+1+8). __wakeup() runs on unserialize and often
  resets properties — the CVE-2016-7124 trick skips it by making the DECLARED property count
  larger than the object really has (change O:4:"Name":2: to O:4:"Name":3:). __destruct()
  runs at end of script. Read the class definition first so names, sizes, and order match.

Flags look like flag{...}. Only report a flag you actually saw in a response.
When you have it, end your final message with the flag on its own line."""


DIAGNOSTIC = """When stuck or repeating yourself, run these checks:
- The challenge title/description usually names the vulnerability class directly (e.g.
  "EasySQL" = SQL injection, "SSRF" = SSRF). Make that your FIRST hypothesis — don't let an
  unrelated file (robots.txt, a "secretkey.txt", ...) derail you into guessing a different bug.
- SQLi: confirm where the parameter actually goes — GET ?query= vs POST body — then test the
  smallest payloads (1, ', 1' or '1'='1) and read the response difference (error / echo / a
  "Nonono"-style filter). A common bypass when select/union/from/where are filtered is `*,1`.
- If the response looks "static", first check it isn't gzipped/truncated or that you're using
  the wrong parameter name — don't jump to "not <vuln class>" before ruling those out."""


def web_tools(target: str, client: httpx.Client) -> list[Tool]:
    return [http_tool(target, client), http_batch_tool(target, client), python_tool(), phar_tool()]


def web_tools_multi(
    urls: list[str], client: httpx.Client, workdir: Path | None = None
) -> list[Tool]:
    """Custom-target tools: one http_request/http_batch that can hit any of several origins
    (via a 0-based 'target' argument), a download_file tool that saves raw bytes into the
    workspace, run_python pointed at that same workspace (so it can read downloaded files),
    plus a phar generator for phar deserialization."""
    return [multi_http_tool(urls, client), multi_http_batch_tool(urls, client),
            download_tool(urls, client, workdir), python_tool(workdir), phar_tool()]


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
