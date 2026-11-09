"""Offline test of the crypto loop: a scripted fake model writes real break code that
runs in the real sandbox. No API key, no network to a model.

Usage: python crypto/test_offline.py
"""

import secrets
from types import SimpleNamespace

import agent  # sets up sys.path so core/ is importable
from challenges import xor_single
from core.agent import FLAG_PATTERN, run_loop
from core.sandbox import python_tool


def main() -> None:
    flag = f"flag{{{secrets.token_hex(12)}}}"
    challenge = xor_single.make(flag)
    hex_ct = challenge.split("ciphertext (hex): ")[1].strip()

    # The fake model: brute-force the single-byte XOR in the sandbox, then report.
    def fake_chat(messages, schemas):
        if not any(m["role"] == "tool" for m in messages):
            code = (
                f"ct=bytes.fromhex('{hex_ct}')\n"
                "for k in range(256):\n"
                "    p=bytes(b^k for b in ct)\n"
                "    if p.startswith(b'flag{'):\n"
                "        print(p.decode());break\n"
            )
            return SimpleNamespace(
                content="Brute-forcing the key.",
                tool_calls=[
                    SimpleNamespace(
                        id="c1",
                        function=SimpleNamespace(name="run_python", arguments=f'{{"code": {code!r}}}'),
                    )
                ],
            )
        last_tool = [m for m in messages if m["role"] == "tool"][-1]["content"]
        found = FLAG_PATTERN.search(last_tool)
        return SimpleNamespace(content=f"Recovered.\n{found.group(0)}", tool_calls=None)

    final_text, calls = run_loop(
        fake_chat, [python_tool()], agent.SYSTEM_PROMPT, challenge, max_turns=10
    )
    recovered = FLAG_PATTERN.findall(final_text)
    ok = bool(recovered) and recovered[-1] == flag
    print(f"run_python calls: {calls}  recovered flag matches: {ok}")
    assert ok, f"expected {flag!r}, got {final_text!r}"
    print("PASS offline crypto test")


if __name__ == "__main__":
    main()
