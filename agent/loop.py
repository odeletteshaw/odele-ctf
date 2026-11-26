"""The model-agnostic agent loop shared by every challenge category.

A category supplies a list of Tools and the two prompts; this module runs the
OpenAI-compatible tool-calling loop and extracts the flag. Nothing here is specific
to web, crypto, pwn, etc.
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI

from . import config

# Flag contents may contain spaces (e.g. a URL-encoded payload decodes to "flag{and 1=1}").
# Only '}' terminates the match, but keep out newlines and quotes so a stray "flag{…" in the
# model's reasoning text is never captured as the whole paragraph.
FLAG_PATTERN = re.compile(r"flag\{[^}\n\"']+\}")

# A malformed tool call must not poison the conversation: echoing a huge argument blob
# back as the tool error makes the next model turn imitate and re-wrap it (observed:
# 8 KB -> 51 KB -> 514 KB, then 20 minutes of invalid JSON). Cap what we accept and
# what we echo, and nudge after consecutive failures.
MAX_TOOL_ARGS_CHARS = 20_000
INVALID_ARGS_PREVIEW = 300
# Fallback for targets whose flag uses a different keyword (ctf{...}, answer{...}, ...).
# Require a >=3-char prefix so code/regex fragments like "d{11}", "s{14}", "n{2}" (from
# \d{11}, s:14, ...) are never mistaken for a flag.
GENERAL_FLAG_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,}\{[^}\n\"']+\}")


def _is_placeholder_flag(flag: str) -> bool:
    """True for literal placeholders like 'flag{...}' — a matched token with no alphanumeric
    payload, which is the model echoing an example rather than a real recovered flag."""
    if "{" not in flag or "}" not in flag:
        return True
    inner = flag[flag.index("{") + 1:flag.rindex("}")]
    return not re.search(r"[A-Za-z0-9]", inner)


def extract_flags(text: str, pattern: "re.Pattern[str] | None" = None) -> list[str]:
    """All non-placeholder flags in `text`: the given pattern (or FLAG_PATTERN) first,
    falling back to GENERAL_FLAG_PATTERN for targets with a different keyword prefix."""
    found = [f for f in (pattern or FLAG_PATTERN).findall(text) if not _is_placeholder_flag(f)]
    if not found:
        found = [f for f in GENERAL_FLAG_PATTERN.findall(text) if not _is_placeholder_flag(f)]
    return found


@dataclass
class Tool:
    """One capability the model may call. The handler takes parsed JSON args and
    returns the text the model sees back.

    `repeat_key` (optional) maps args to a JSON-able fingerprint used by the loop's
    repeated-call detector. Give it to tools where two calls can be "the same request"
    without identical JSON — e.g. an HTTP tool keyed on method+path+body, so retrying
    the same endpoint with a changing Cookie header still counts as a repeat."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]
    repeat_key: Callable[[dict[str, Any]], Any] | None = None

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
    diagnostic: str | None = None,
) -> tuple[str, int]:
    def emit(event: dict[str, Any]) -> None:
        # Timestamp every event: transcripts can then tell "the model thought for 20
        # minutes" apart from "the tool was slow" without trusting HTTP Date headers.
        if on_event:
            on_event({**event, "ts": time.time()})

    handlers = {tool.name: tool.handler for tool in tools}
    repeat_key_fns = {tool.name: tool.repeat_key for tool in tools}
    schemas = [tool.schema() for tool in tools]
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    final_text = ""
    tool_calls = 0
    repeat_counts: dict[tuple[str, str], int] = {}
    last_output: dict[tuple[str, str], str] = {}
    agent_text_counts: dict[str, int] = {}
    flag_hint_sent = False
    invalid_streak = 0
    invalid_total = 0
    seen_flags: set[str] = set()
    flag_verify_nudged = False
    for _ in range(max_turns):
        # Fold in any supervisor guidance before the model's next turn.
        if guidance and (note := guidance()):
            messages.append({"role": "user", "content": f"[Supervisor guidance] {note}"})
            print(f"[guidance] {note}", flush=True)
            emit({"type": "guidance", "text": note})

        message = chat(messages, schemas)
        assistant: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.content:
            final_text = message.content
            norm_text = " ".join(message.content.split())
            agent_text_counts[norm_text] = agent_text_counts.get(norm_text, 0) + 1
            print(f"[agent] {message.content}", flush=True)
            emit({"type": "agent", "text": message.content})
        if not message.tool_calls:
            messages.append(assistant)
            text = message.content or ""
            found = extract_flags(text, flag_pattern)
            has_flag = bool(text.strip()) and bool(found)
            # A reported flag that never appeared verbatim in a tool result was probably
            # retyped from memory (observed: one wrong hex char). Ask for verification once
            # before accepting the conclusion; repeating it then ends normally.
            unseen = [f for f in found if f not in seen_flags]
            if has_flag and unseen and not flag_verify_nudged:
                flag_verify_nudged = True
                messages.append({
                    "role": "user",
                    "content": (
                        f"The flag(s) {', '.join(unseen)} do not appear verbatim in any tool "
                        "output. Verify the exact characters against the source before "
                        "concluding: re-read the tool result, or re-decode/convert it in "
                        "run_python, and copy the string exactly instead of retyping it. If you "
                        "are certain it was assembled from several outputs, restate it and stop."
                    ),
                })
                print("[nudge] reported flag not seen in tool output — verify it", flush=True)
                emit({"type": "guidance",
                      "text": "(auto) reported flag not seen in tool output — verify it"})
                continue
            # A text conclusion ends the loop when it has the flag, or when persistence is
            # off (so the model may legitimately answer "couldn't solve"). In persist mode,
            # text without a flag is treated as a premature stop and nudged to continue.
            if has_flag or (text.strip() and not persist):
                break
            norm_text = " ".join(text.split())
            if agent_text_counts.get(norm_text, 0) >= 3:
                # The model is stuck repeating the same message without calling a tool —
                # stop instead of burning every remaining turn on an identical reply.
                print("[loop] repeated output, stopping", flush=True)
                emit({"type": "guidance", "text": "(auto) stopped — repeated output without progress"})
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
        # Keep an oversized argument blob out of the context we resend; the tool message
        # carries the actionable error, so the echoed call can be truncated safely.
        for call_dict in assistant["tool_calls"]:
            args_text = call_dict["function"]["arguments"] or ""
            if len(args_text) > MAX_TOOL_ARGS_CHARS:
                call_dict["function"]["arguments"] = args_text[:2000] + "…[truncated]"
        messages.append(assistant)
        seen_this_turn: list[tuple[str, str]] = []
        found_in_output: str | None = None
        for call in message.tool_calls:
            tool_calls += 1
            raw_args = call.function.arguments or ""
            oversized = len(raw_args) > MAX_TOOL_ARGS_CHARS
            try:
                args = None if oversized else json.loads(raw_args or "{}")
                canon = json.dumps(args, sort_keys=True)
            except (json.JSONDecodeError, TypeError):
                args = None
                canon = raw_args
            # Fingerprint the call for the repeat detector: a tool may collapse
            # cosmetic differences (e.g. a changing header) onto the same key.
            key = (call.function.name, canon)
            fingerprint = repeat_key_fns.get(call.function.name)
            if isinstance(args, dict) and fingerprint is not None:
                try:
                    key = (call.function.name,
                           json.dumps(fingerprint(args), sort_keys=True, default=str))
                except Exception:
                    pass
            repeat_counts[key] = repeat_counts.get(key, 0) + 1
            seen_this_turn.append(key)
            if oversized:
                invalid_streak += 1
                invalid_total += 1
                output = (
                    f"Error: tool arguments were too large ({len(raw_args)} chars; limit "
                    f"{MAX_TOOL_ARGS_CHARS}; the call was not executed). Build long payloads "
                    "in run_python and pass the compact result (hex/base64), not a giant "
                    "literal. If you are repeating one padding/escape sequence, compute the "
                    "exact short value instead — hundreds of repeats is a generation error."
                )
            elif args is None:
                invalid_streak += 1
                invalid_total += 1
                preview = (raw_args if len(raw_args) <= INVALID_ARGS_PREVIEW
                           else raw_args[:INVALID_ARGS_PREVIEW] + "…")
                output = (
                    "Error: tool arguments were not valid JSON; the call was not executed. "
                    "Re-send ONE minimal valid JSON object — do not wrap JSON inside a string. "
                    f"Received (truncated): {preview}"
                )
            elif found_in_output is not None:
                # A previous call in this same turn already produced the flag. Still answer
                # the protocol (one tool message per call id) but don't execute the rest.
                output = ("Skipped: an earlier tool call in this turn already returned the "
                          "flag. Report it in your final message now instead of probing further.")
            else:
                invalid_streak = 0
                print(f"[{call.function.name}] {args}", flush=True)
                emit({"type": "tool_call", "name": call.function.name, "args": args})
                handler = handlers.get(call.function.name)
                output = handler(args) if handler else f"Error: unknown tool {call.function.name}"
            last_output[key] = " ".join(str(output).split())
            emit({"type": "tool_result", "name": call.function.name, "output": output})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            matches = extract_flags(str(output), flag_pattern)
            if matches:
                seen_flags.update(matches)
                if found_in_output is None and not flag_hint_sent:
                    found_in_output = matches[-1]
        # Two bad argument blobs in a row usually means the model is imitating its own
        # malformed output. Stop the spiral before it grows (and before it fills the context).
        stalled = False
        invalid_nudged = False
        if invalid_streak >= 2:
            invalid_nudged = True
            invalid_streak = 0
            note = (
                "Your recent tool calls had invalid JSON arguments. Stop and send ONE minimal, "
                "valid JSON call. Do not put JSON inside another JSON string; for a long "
                "payload, compute it in run_python and pass a short hex/base64 value."
            )
            if diagnostic:
                note += "\n\nDiagnostic checklist:\n" + diagnostic
            messages.append({"role": "user", "content": note})
            print("[nudge] invalid tool arguments — send minimal valid JSON", flush=True)
            emit({"type": "guidance", "text": "(auto) invalid tool arguments — send minimal valid JSON"})
        if invalid_total >= 6:
            stalled = True
            print("[loop] stalled on invalid tool arguments, stopping", flush=True)
            emit({"type": "guidance",
                  "text": "(auto) stopped — repeated invalid tool arguments"})
            break
        # The flag may already be sitting in a tool result while the model keeps probing.
        # Tell it to report that value now; solve() only extracts the flag from the final
        # assistant message, so this nudge (not an early stop) is what converts it to PASS.
        if found_in_output is not None:
            flag_hint_sent = True
            messages.append({
                "role": "user",
                "content": (
                    f"A tool output already contains the flag {found_in_output}. Stop calling "
                    "tools and report it in your final message now."
                ),
            })
            print("[nudge] flag already found — report it", flush=True)
            emit({"type": "guidance", "text": "(auto) flag already found — report it"})
        # Break tool-call loops: if the model repeats an exact call it already made, inject a
        # supervisor note telling it to review its earlier findings and change tack instead of
        # burning the turn budget on the same doomed attempt. Once a flag has surfaced, the
        # "report it now" note above is the only instruction worth sending.
        for key in seen_this_turn:
            if flag_hint_sent or invalid_nudged:
                break
            count = repeat_counts[key]
            if count >= 10:
                stalled = True
                break
            if count in (2, 5, 8):
                # Escalate with evidence: quote the identical response so the model can see
                # that replaying the request cannot produce a new result.
                seen = last_output.get(key, "")[:200]
                nudge = (
                    f"You have sent this same request {count} times. The last response was: "
                    f"{seen!r}. Repeating it will not change the answer. Recompute the payload "
                    "from scratch in run_python — print the exact bytes/blocks you expect and "
                    "verify the arithmetic — then send a DIFFERENT request."
                )
                if diagnostic:
                    nudge += "\n\nDiagnostic checklist:\n" + diagnostic
                messages.append({"role": "user", "content": nudge})
                print(f"[nudge] same request {count}x — response unchanged", flush=True)
                emit({"type": "guidance",
                      "text": f"(auto) same request {count}× — response unchanged"})
        if stalled:
            print("[loop] stalled on one repeated request, stopping", flush=True)
            emit({"type": "guidance",
                  "text": "(auto) stopped — same request repeated without progress"})
            break
    return final_text, tool_calls


def _openai_chat_fn(client: OpenAI, model: str) -> ChatFn:
    def chat(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Any:
        started = time.time()
        response = client.chat.completions.create(
            model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0,
            timeout=config.API_TIMEOUT,
        )
        elapsed = time.time() - started
        if elapsed > 30:
            print(f"[slow] model call took {elapsed:.0f}s", flush=True)
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
    diagnostic: str | None = None,
) -> SolveResult:
    if not config.API_KEY:
        raise RuntimeError("No API key. Set DEEPSEEK_API_KEY (or CTF_API_KEY), e.g. in .env")
    client = OpenAI(base_url=config.API_BASE, api_key=config.API_KEY,
                    max_retries=config.API_RETRIES)
    chat = _openai_chat_fn(client, model or config.DEFAULT_MODEL)
    final_text, tool_calls = run_loop(
        chat, tools, system_prompt, user_prompt, max_turns,
        on_event=on_event, guidance=guidance, flag_pattern=flag_pattern, persist=persist,
        diagnostic=diagnostic,
    )
    flags = extract_flags(final_text, flag_pattern)
    return SolveResult(flags[-1] if flags else None, final_text, tool_calls)


def generate_writeup(
    user: str,
    events: list[dict[str, Any]],
    flag: str | None,
    model: str | None = None,
) -> str:
    """Synthesize a concise Chinese writeup (题解) from a solve's event stream.

    Returns "" on failure (so a writeup never affects the solve's PASS/FAIL verdict).
    """
    if not config.API_KEY:
        return ""
    client = OpenAI(base_url=config.API_BASE, api_key=config.API_KEY,
                    max_retries=config.API_RETRIES)
    lines: list[str] = []
    for ev in events[-60:]:  # keep the recent tail so the prompt stays bounded
        kind = ev.get("type")
        if kind == "agent":
            lines.append(f"[agent] {ev.get('text', '')}")
        elif kind == "tool_call":
            lines.append(f"[tool {ev.get('name', '?')}] {ev.get('args', '')}")
        elif kind == "tool_result":
            out = str(ev.get("output", ""))
            if len(out) > 800:
                out = out[:800] + " …"
            lines.append(f"[result] {out}")
        elif kind == "guidance":
            lines.append(f"[you] {ev.get('text', '')}")
    transcript = "\n".join(lines)
    prompt = (
        "你刚刚解完一道 CTF 题。请根据下面的题目和解题过程，写一份简洁的中文题解，"
        "包含这几节：题目、思路/漏洞、关键步骤、最终 flag。只写 transcript 里真实发生的内容，"
        "不要编造，约 200–400 字。\n\n"
        f"=== 题目 ===\n{user}\n\n=== 解题过程 ===\n{transcript}\n\n"
        f"最终 flag：{flag or '（未解出）'}\n\n写题解："
    )
    try:
        response = client.chat.completions.create(
            model=model or config.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            timeout=config.API_TIMEOUT,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as error:  # noqa: BLE001
        print(f"[writeup] generation failed: {error}", flush=True)
        return ""
