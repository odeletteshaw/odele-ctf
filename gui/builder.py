"""Build the pieces of one solve task from a spec. Runs INSIDE the worker process,
because the tools hold live resources (an HTTP client, a challenge server) that must
live in the same process as the solve.

A spec is a small picklable dict:
  {"kind": "benchmark", "category": "web", "name": "sqli_login"}
  {"kind": "custom", "url": "https://...", "description": "...", "flag_prefix": "flag"}
"""

import importlib
import secrets
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import Tool  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

Built = tuple[str | None, list[Tool], str, str, Callable[[], None]]


def list_challenges(category: str) -> list[str]:
    folder = Path(__file__).resolve().parent.parent / category / "challenges"
    return sorted(p.stem for p in folder.glob("*.py") if not p.stem.startswith("_"))


def _benchmark(category: str, name: str) -> Built:
    flag = f"flag{{{secrets.token_hex(12)}}}"
    challenge = importlib.import_module(f"{category}.challenges.{name}")
    agent = importlib.import_module(f"{category}.agent")
    if category == "web":
        server, url = challenge.start(flag)
        client = agent.new_http_client()
        tools = agent.web_tools(url, client)
        user = f"Target: {url}\n\nChallenge description: {challenge.DESCRIPTION}"

        def cleanup() -> None:
            server.shutdown()
            client.close()

        return flag, tools, agent.SYSTEM_PROMPT, user, cleanup
    if category in ("crypto", "misc", "forensics"):  # text-in, run_python-only categories
        result = challenge.make(flag)
        if category == "forensics" and hasattr(result, "dir"):  # workspace-based large artifact
            return flag, [python_tool(result.dir)], agent.WORKSPACE_SYSTEM_PROMPT, challenge.DESCRIPTION, result.cleanup
        return flag, [python_tool()], agent.SYSTEM_PROMPT, result, lambda: None
    if category == "ai":  # live guarded chatbot reached via send_message
        defender = challenge.make(flag)
        tools = agent.redteam_tools(defender)
        user = agent.attacker_prompt(challenge.DESCRIPTION)
        return flag, tools, agent.SYSTEM_PROMPT, user, defender.close
    if category == "pwn":  # simulated vulnerable process reached via send_input
        proc = challenge.make(flag)
        tools = agent.pwn_tools(proc)
        return flag, tools, agent.SYSTEM_PROMPT, challenge.DESCRIPTION, lambda: None
    if category == "reverse":  # compiled crackme reached via disassemble + run_binary
        target = challenge.make(flag)
        tools = agent.reverse_tools(target)
        return flag, tools, agent.SYSTEM_PROMPT, challenge.DESCRIPTION, target.cleanup
    raise ValueError(f"unsupported category: {category}")


def _custom(url: str, description: str) -> Built:
    """A real external target: the agent gets the web toolset (http + run_python), the
    http tool locked to this origin. No known flag — any flag found is reported."""
    web = importlib.import_module("web.agent")
    client = web.new_http_client()
    tools = web.web_tools(url, client)
    user = f"Target: {url}\n\nChallenge description: {description or '(none given)'}"
    return None, tools, web.SYSTEM_PROMPT, user, client.close


def build_task(spec: dict[str, Any]) -> Built:
    kind = spec.get("kind")
    if kind == "benchmark":
        return _benchmark(spec["category"], spec["name"])
    if kind == "custom":
        return _custom(spec["url"], spec.get("description", ""))
    raise ValueError(f"unknown task kind: {kind}")
