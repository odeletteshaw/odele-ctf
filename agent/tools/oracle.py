"""An interactive oracle the agent queries in batches: send a list of inputs, get one answer
per input (indexed). This makes multi-query attacks — padding oracle, RSA LSB oracle, ECB
byte-at-a-time — feasible within a bounded number of turns."""

from agent.loop import Tool

MAX_BATCH = 300


def oracle_tool(name: str, description: str, oracle, value_desc: str) -> Tool:
    """oracle(data: bytes) -> str is the check. The tool batches `inputs` (hex strings)
    through it and returns one answer per input, prefixed with its index."""

    def handler(args: dict) -> str:
        inputs = args.get("inputs", [])
        if len(inputs) > MAX_BATCH:
            return f"Error: too many queries ({len(inputs)} > {MAX_BATCH}); split the batch."
        lines = []
        for idx, raw in enumerate(inputs):
            try:
                # Tolerate spaced / 0x-prefixed hex ("de ad", "0xdead") — otherwise a
                # cosmetic format error fails the whole multi-query attack batch.
                clean = "".join(str(raw).split()).removeprefix("0x")
                data = bytes.fromhex(clean)
                lines.append(f"{idx}: {oracle(data)}")
            except ValueError as error:
                lines.append(f"{idx}: error: invalid hex ({error})")
            except Exception as error:
                lines.append(f"{idx}: error: {error}")
        return "\n".join(lines)

    return Tool(
        name=name,
        description=description,
        parameters={
            "type": "object",
            "properties": {
                "inputs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": f"List of {value_desc} strings to query the oracle with (up to {MAX_BATCH} per call).",
                }
            },
            "required": ["inputs"],
        },
        handler=handler,
    )
