"""Helpers for the offline (no API key) loop tests: drive run_loop with a scripted fake
model that returns hand-built tool-call messages, then check the recovered flag."""

import json
from types import SimpleNamespace


def tool_call(call_id: str, name: str, args: dict) -> SimpleNamespace:
    """One OpenAI-style tool_call the fake model can return in its message."""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )
