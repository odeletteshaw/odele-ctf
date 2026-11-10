"""The pwn category's new agent capability and its harness.

Pwn is hermetic the same way web is: we never run a real vulnerable binary or spawn a real
shell. Instead each challenge is a SIMULATED target process whose vulnerability plays out
against virtual memory — a modeled stack, an auth flag next to a buffer, a toy printf that
reads a virtual stack. The agent pokes it through the `send_input` tool (send bytes, read
the program's output), exactly as it would pipe a payload to a real process, and uses
run_python to compute offsets and pack addresses.

Split, as everywhere:
  - Process (+ subclasses in challenges/)  = HARNESS. Holds the flag and the virtual memory.
    The agent never imports it.
  - process_tool(proc)                     = the agent capability bound to one target.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import Tool  # noqa: E402

MAX_INPUT = 4096  # bytes; a sane cap on a single payload


class Process:
    """A simulated target. send(data) feeds one payload to the program and returns whatever
    it prints. Single-shot by default; stateful subclasses may override as needed."""

    def send(self, data: bytes) -> str:
        raise NotImplementedError


def process_tool(proc: Process) -> Tool:
    """send_input: deliver a payload to the target process and read its output. Payload bytes
    come in as hex (preferred for non-printable bytes like packed addresses) or as text."""

    def handler(args: dict) -> str:
        if "hex" in args and args["hex"]:
            try:
                data = bytes.fromhex("".join(str(args["hex"]).split()))
            except ValueError as error:
                return f"Error: hex was not valid: {error}"
        else:
            data = str(args.get("text", "")).encode()
        if len(data) > MAX_INPUT:
            return f"Error: payload too large ({len(data)} > {MAX_INPUT} bytes)."
        try:
            return proc.send(data)
        except Exception as error:  # a simulated crash is information, not a failure
            return f"[process crashed] {error}"

    return Tool(
        name="send_input",
        description=(
            "Send a payload to the target process and return its output. Provide the payload "
            "as 'hex' (hex-encoded bytes, best for packed addresses and non-printable bytes) "
            "or as 'text' (UTF-8). Compute payloads with run_python, then send the hex."
        ),
        parameters={
            "type": "object",
            "properties": {
                "hex": {"type": "string", "description": "Hex-encoded payload bytes."},
                "text": {"type": "string", "description": "UTF-8 payload (alternative to hex)."},
            },
        },
        handler=handler,
    )
