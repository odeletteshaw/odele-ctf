"""The send_input agent capability (deliver a payload to a simulated target process)."""

from core.agent import Tool

MAX_INPUT = 4096  # bytes; a sane cap on a single payload


def process_tool(proc) -> Tool:
    """send_input: deliver a payload to the target process and read its output. Payload
    bytes come in as hex (preferred for non-printable bytes like packed addresses) or text.
    `proc` is any object with a send(bytes) -> str method."""

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
