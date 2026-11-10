"""Offline test of the reverse tools + shared loop: a scripted fake model drives the real
disassemble and run_binary tools against a real compiled crackme. No API key.

Usage: python reverse/test_offline.py
"""

import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import FLAG_PATTERN, run_loop  # noqa: E402
from core.offline import tool_call  # noqa: E402
from reverse.agent import reverse_tools  # noqa: E402
from reverse.challenges import run_me  # noqa: E402
from tools.bin import disassemble_tool, run_binary_tool  # noqa: E402


def main() -> None:
    flag = f"flag{{{secrets.token_hex(12)}}}"
    target = run_me.make(flag)
    try:
        # Verify each tool directly, independent of the loop.
        disasm = disassemble_tool(target.binary).handler({})
        assert "_main" in disasm, "disassemble did not find main"
        run_out = run_binary_tool(target.binary).handler({"stdin": ""})
        assert flag in run_out, f"run_binary did not print the flag: {run_out!r}"

        # Drive the full loop with a scripted model: disassemble, run, then report the flag.
        state = {"turn": 0}

        def fake_chat(messages, schemas):
            state["turn"] += 1
            if state["turn"] == 1:
                return SimpleNamespace(
                    content="Disassembling.",
                    tool_calls=[tool_call("c1", "disassemble", {})],
                )
            if state["turn"] == 2:
                return SimpleNamespace(
                    content="Running it.",
                    tool_calls=[tool_call("c2", "run_binary", {"stdin": ""})],
                )
            last_tool = [m for m in messages if m["role"] == "tool"][-1]["content"]
            found = FLAG_PATTERN.search(last_tool)
            assert found, last_tool
            return SimpleNamespace(content=f"Done.\n{found.group(0)}", tool_calls=None)

        final_text, calls = run_loop(
            fake_chat, reverse_tools(target), "test", run_me.DESCRIPTION, max_turns=10
        )
        recovered = FLAG_PATTERN.findall(final_text)
        ok = bool(recovered) and recovered[-1] == flag
        print(f"tool calls: {calls}  recovered flag matches: {ok}")
        assert ok, f"expected {flag!r}, got {final_text!r}"
        print("PASS offline loop test")
    finally:
        target.cleanup()


if __name__ == "__main__":
    main()
