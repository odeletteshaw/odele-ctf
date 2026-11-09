"""The model-agnostic agent loop shared by every challenge category.

A category supplies a list of Tools and the two prompts; this module runs the
OpenAI-compatible tool-calling loop and extracts the flag. Nothing here is specific
to web, crypto, pwn, etc.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI

from . import config

FLAG_PATTERN = re.compile(r"flag\{[^}\s]+\}")


@dataclass
class Tool:
    """One capability the model may call. The handler takes parsed JSON args and
    returns the text the model sees back."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class SolveResult:
    flag: str | None
    final_text: str
    tool_calls: int


# A chat function takes (messages, tool schemas) and returns one assistant message
# exposing .content (str | None) and .tool_calls (each with .id and
# .function.name / .function.arguments). Real runs use OpenAI; tests inject a fake.
ChatFn = Callable[[list[dict[str, Any]], list[dict[str, Any]]], Any]


def run_loop(
    chat: ChatFn, tools: list[Tool], system: str, user: str, max_turns: int
) -> tuple[str, int]:
    handlers = {tool.name: tool.handler for tool in tools}
    schemas = [tool.schema() for tool in tools]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    final_text = ""
    tool_calls = 0
    for _ in range(max_turns):
        message = chat(messages, schemas)
        assistant: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.content:
            print(f"[agent] {message.content}", flush=True)
            final_text = message.content
        if not message.tool_calls:
            messages.append(assistant)
            break
        assistant["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls
        ]
        messages.append(assistant)
        for call in message.tool_calls:
            tool_calls += 1
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError as error:
                output = f"Error: arguments were not valid JSON: {error}"
            else:
                print(f"[{call.function.name}] {args}", flush=True)
                handler = handlers.get(call.function.name)
                output = handler(args) if handler else f"Error: unknown tool {call.function.name}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
    return final_text, tool_calls


def _openai_chat_fn(client: OpenAI, model: str) -> ChatFn:
    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        response = client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0
        )
        return response.choices[0].message

    return chat


def solve(
    tools: list[Tool],
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_turns: int = 30,
) -> SolveResult:
    if not config.API_KEY:
        raise RuntimeError("No API key. Set DEEPSEEK_API_KEY (or CTF_API_KEY), e.g. in .env")
    client = OpenAI(base_url=config.API_BASE, api_key=config.API_KEY)
    chat = _openai_chat_fn(client, model or config.DEFAULT_MODEL)
    final_text, tool_calls = run_loop(chat, tools, system_prompt, user_prompt, max_turns)
    flags = FLAG_PATTERN.findall(final_text)
    return SolveResult(flags[-1] if flags else None, final_text, tool_calls)
