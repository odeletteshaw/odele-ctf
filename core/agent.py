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
# Fallback for targets whose flag uses a different keyword (ctf{...}, answer{...}, ...).
GENERAL_FLAG_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*\{[^}\s]+\}")


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

# An event sink receives structured dicts describing each step (for a GUI or logger).
# A guidance source is polled before each model turn; any text it returns is injected
# into the conversation as a supervisor note. Both are optional and default to no-ops.
EventFn = Callable[[dict[str, Any]], None]
GuidanceFn = Callable[[], str | None]


def run_loop(
    chat: ChatFn,
    tools: list[Tool],
    system: str,
    user: str,
    max_turns: int,
    on_event: EventFn | None = None,
    guidance: GuidanceFn | None = None,
    flag_pattern: "re.Pattern[str] | None" = None,
    persist: bool = False,
) -> tuple[str, int]:
    def emit(event: dict[str, Any]) -> None:
        if on_event:
            on_event(event)

    handlers = {tool.name: tool.handler for tool in tools}
    schemas = [tool.schema() for tool in tools]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    final_text = ""
    tool_calls = 0
    repeat_counts: dict[tuple[str, str], int] = {}
    nudged_repeats: set[tuple[str, str]] = set()
    for _ in range(max_turns):
        # Fold in any supervisor guidance before the model's next turn.
        if guidance and (note := guidance()):
            messages.append({"role": "user", "content": f"[Supervisor guidance] {note}"})
            print(f"[guidance] {note}", flush=True)
            emit({"type": "guidance", "text": note})

        message = chat(messages, schemas)
        assistant: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.content:
            print(f"[agent] {message.content}", flush=True)
            final_text = message.content
            emit({"type": "agent", "text": message.content})
        if not message.tool_calls:
            messages.append(assistant)
            pattern = flag_pattern or FLAG_PATTERN
            text = message.content or ""
            has_flag = bool(text.strip()) and bool(
                pattern.search(text) or GENERAL_FLAG_PATTERN.search(text)
            )
            # A text conclusion ends the loop when it has the flag, or when persistence is
            # off (so the model may legitimately answer "couldn't solve"). In persist mode,
            # text without a flag is treated as a premature stop and nudged to continue.
            if has_flag or (text.strip() and not persist):
                break
            nudge = (
                "You stopped without giving the flag. First review your earlier findings for "
                "anything you may have missed, then try a DIFFERENT approach — do not repeat a "
                "technique that already failed. The challenge is not solved yet."
            )
            messages.append({"role": "user", "content": nudge})
            print("[nudge] keep going", flush=True)
            emit({"type": "guidance", "text": "(auto) keep going"})
            continue
        assistant["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in message.tool_calls
        ]
        messages.append(assistant)
        seen_this_turn: list[tuple[str, str]] = []
        for call in message.tool_calls:
            tool_calls += 1
            raw_args = call.function.arguments or ""
            try:
                canon = json.dumps(json.loads(raw_args or "{}"), sort_keys=True)
            except (json.JSONDecodeError, TypeError):
                canon = raw_args
            key = (call.function.name, canon)
            repeat_counts[key] = repeat_counts.get(key, 0) + 1
            seen_this_turn.append(key)
            try:
                args = json.loads(raw_args or "{}")
            except json.JSONDecodeError as error:
                output = f"Error: arguments were not valid JSON: {error}"
            else:
                print(f"[{call.function.name}] {args}", flush=True)
                emit({"type": "tool_call", "name": call.function.name, "args": args})
                handler = handlers.get(call.function.name)
                output = handler(args) if handler else f"Error: unknown tool {call.function.name}"
            emit({"type": "tool_result", "name": call.function.name, "output": output})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
        # Break tool-call loops: if the model repeats an exact call it already made, inject a
        # supervisor note telling it to review its earlier findings and change tack instead of
        # burning the turn budget on the same doomed attempt.
        for key in seen_this_turn:
            if repeat_counts[key] >= 2 and key not in nudged_repeats:
                nudged_repeats.add(key)
                messages.append({
                    "role": "user",
                    "content": (
                        "You are repeating the exact same tool call you already made. Stop and "
                        "review your earlier findings for anything you missed, then try a "
                        "DIFFERENT approach — do not repeat a technique that already failed."
                    ),
                })
                print("[nudge] repeated call — try something different", flush=True)
                emit({"type": "guidance", "text": "(auto) repeated call — try something different"})
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
    on_event: EventFn | None = None,
    guidance: GuidanceFn | None = None,
    flag_pattern: "re.Pattern[str] | None" = None,
    persist: bool = False,
) -> SolveResult:
    if not config.API_KEY:
        raise RuntimeError("No API key. Set DEEPSEEK_API_KEY (or CTF_API_KEY), e.g. in .env")
    client = OpenAI(base_url=config.API_BASE, api_key=config.API_KEY)
    chat = _openai_chat_fn(client, model or config.DEFAULT_MODEL)
    final_text, tool_calls = run_loop(
        chat, tools, system_prompt, user_prompt, max_turns,
        on_event=on_event, guidance=guidance, flag_pattern=flag_pattern, persist=persist,
    )
    flags = (flag_pattern or FLAG_PATTERN).findall(final_text)
    if not flags:
        flags = GENERAL_FLAG_PATTERN.findall(final_text)
    return SolveResult(flags[-1] if flags else None, final_text, tool_calls)
