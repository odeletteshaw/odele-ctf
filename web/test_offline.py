"""Offline test of the shared agent loop: a scripted fake model drives the real
http_request tool against the real local challenge. No API key, no network to a model.

Usage: python web/test_offline.py
"""

import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import FLAG_PATTERN, run_loop  # noqa: E402
from core.offline import tool_call  # noqa: E402
from web.agent import SYSTEM_PROMPT, new_http_client, web_tools  # noqa: E402
from web.challenges import sqli_login  # noqa: E402


def main() -> None:
    flag = f"flag{{{secrets.token_hex(12)}}}"
    server, url = sqli_login.start(flag)

    # The fake model: first turn sends the SQLi, second turn reads the tool result
    # off the message list and reports the flag it contains.
    def fake_chat(messages, schemas):
        if not any(m["role"] == "tool" for m in messages):
            return SimpleNamespace(
                content="Trying an auth bypass.",
                tool_calls=[
                    tool_call(
                        "c1",
                        "http_request",
                        {
                            "method": "POST",
                            "path": "/login",
                            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
                            "body": "username=admin'--&password=x",
                        },
                    )
                ],
            )
        last_tool = [m for m in messages if m["role"] == "tool"][-1]["content"]
        found = FLAG_PATTERN.search(last_tool)
        return SimpleNamespace(content=f"Done.\n{found.group(0)}", tool_calls=None)

    client = new_http_client()
    try:
        final_text, calls = run_loop(
            fake_chat, web_tools(url, client), SYSTEM_PROMPT, "test", max_turns=10
        )
    finally:
        client.close()
        server.shutdown()

    recovered = FLAG_PATTERN.findall(final_text)
    ok = bool(recovered) and recovered[-1] == flag
    print(f"tool calls: {calls}  recovered flag matches: {ok}")
    assert ok, f"expected {flag!r}, got {final_text!r}"
    print("PASS offline loop test")


if __name__ == "__main__":
    main()
