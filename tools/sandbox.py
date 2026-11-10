"""The run_python agent capability. The sandbox engine lives in core/sandbox.py; this
module only wraps it as a Tool, shared by every challenge category."""

from core.agent import Tool
from core.sandbox import run_python


def python_tool() -> Tool:
    return Tool(
        name="run_python",
        description=(
            "Run Python 3 code in an isolated subprocess (no network, time-limited, "
            "ephemeral temp dir) and return its stdout/stderr. Use it for anything that "
            "needs real computation: base64/hex, hashing and HMAC, signing or forging "
            "tokens, brute-forcing a weak secret, or breaking a cipher. Print your results."
        ),
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python 3 source to run"}},
            "required": ["code"],
        },
        handler=lambda args: run_python(args.get("code", "")),
    )
