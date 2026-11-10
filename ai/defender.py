"""The guarded chatbot the red-team agent attacks — the AI category's equivalent of the
web harness. It is HARNESS, not a tool: the flag lives in its system prompt and the agent
can only reach it through the `send_message` tool, never by importing this module.

A Defender wraps a real LLM (the same provider the agent uses) holding a secret flag, plus
two optional mechanical guards that sit around the model:

  input_guard(message)  -> str | None   a canned refusal if the message is blocked, else None
  output_guard(reply, flag) -> str      the reply after redaction/transformation

Guards are deliberately simple and separate from the model's own willingness to talk: the
challenges tune both the system prompt (how firmly the model refuses) and the guards (what
a dumb filter catches) to build a difficulty ladder. The classic seam is an output_guard
that only catches the *verbatim* flag — a base64 or spaced-out flag slips through.
"""

from typing import Callable

from openai import OpenAI

from core import config

InputGuard = Callable[[str], str | None]
OutputGuard = Callable[[str, str], str]


class Defender:
    def __init__(
        self,
        flag: str,
        system_prompt: str,
        input_guard: InputGuard | None = None,
        output_guard: OutputGuard | None = None,
        model: str | None = None,
    ) -> None:
        self.flag = flag
        self.system_prompt = system_prompt
        self.input_guard = input_guard
        self.output_guard = output_guard
        self.model = model or config.DEFAULT_MODEL
        self._client = OpenAI(base_url=config.API_BASE, api_key=config.API_KEY)
        self._history: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    def send(self, message: str) -> str:
        """One red-team turn: input guard, model reply, output guard. Keeps a running
        conversation so multi-turn attacks (roleplay build-up, context stuffing) work."""
        if self.input_guard is not None:
            refusal = self.input_guard(message)
            if refusal is not None:
                return refusal  # blocked before the model ever sees it
        self._history.append({"role": "user", "content": message})
        response = self._client.chat.completions.create(
            model=self.model, messages=self._history, temperature=0
        )
        reply = response.choices[0].message.content or ""
        self._history.append({"role": "assistant", "content": reply})
        if self.output_guard is not None:
            reply = self.output_guard(reply, self.flag)
        return reply

    def close(self) -> None:
        self._client.close()


# ---- reusable guards the challenges compose ------------------------------------------


def redact_verbatim(reply: str, flag: str) -> str:
    """Block only the literal flag. The intended seam: a transformed flag passes."""
    return reply.replace(flag, "[REDACTED BY OUTPUT FILTER]")


def block_words(words: list[str], refusal: str) -> InputGuard:
    """Reject any message containing one of these words (case-insensitive substring)."""
    lowered = [w.lower() for w in words]

    def guard(message: str) -> str | None:
        low = message.lower()
        if any(w in low for w in lowered):
            return refusal
        return None

    return guard
