"""The send_message agent capability (talk to a guarded target chatbot)."""

from core.agent import Tool


def message_tool(send) -> Tool:
    """send_message, bound to a `send(message: str) -> str` callback that reaches the
    target. Keeps target errors in-band so a broken turn doesn't abort the run."""

    def handler(args: dict) -> str:
        message = str(args.get("message", "")).strip()
        if not message:
            return "Error: message was empty."
        try:
            return send(message)
        except Exception as error:  # surface target/API errors to the agent, keep going
            return f"Error talking to target: {error}"

    return Tool(
        name="send_message",
        description="Send a message to the guarded target chatbot and return its reply.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What to say to the target."}
            },
            "required": ["message"],
        },
        handler=handler,
    )
