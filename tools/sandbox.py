"""The run_python agent capability. The sandbox engine lives in core/sandbox.py; this
module only wraps it as a Tool, shared by every challenge category."""

from pathlib import Path

from core.agent import Tool
from core.sandbox import run_python


def python_tool(workdir: Path | None = None) -> Tool:
    """run_python. With a `workdir`, the sandbox runs in that persistent directory, so the
    code can read files a challenge placed there and keep state across calls."""
    description = (
        "Run Python 3 code in an isolated subprocess (no network, time-limited) and return "
        "its stdout/stderr. Use it for anything that needs real computation: base64/hex, "
        "hashing and HMAC, signing or forging tokens, brute-forcing a weak secret, or "
        "breaking a cipher. Print your results."
    )
    if workdir is not None:
        description += (
            " Your code runs in a PERSISTENT working directory that already holds the "
            "challenge's artifact files — list them with os.listdir('.') and read them with "
            "open(); they stay on disk across calls, so read from disk instead of re-pasting."
        )
    return Tool(
        name="run_python",
        description=description,
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python 3 source to run"}},
            "required": ["code"],
        },
        handler=lambda args: run_python(args.get("code", ""), workdir=workdir),
    )
