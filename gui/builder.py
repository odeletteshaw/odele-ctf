"""Build the pieces of one solve task from a spec. Runs INSIDE the worker process,
because the tools hold live resources (an HTTP client, a challenge server) that must
live in the same process as the solve.

A spec is a small picklable dict:
  {"kind": "benchmark", "category": "web", "name": "sqli_login"}
  {"kind": "custom", "url": "https://...", "description": "...", "flag_prefix": "flag"}
"""

import importlib
import secrets
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import Tool  # noqa: E402
from knowledge import load_techniques  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

Built = tuple[str | None, list[Tool], str, str, Callable[[], None]]


def _system_with_techniques(system: str, category: str) -> str:
    """Append the category's reusable technique cards to the system prompt."""
    tech = load_techniques(category)
    if tech:
        return system + (
            "\n\n--- Reference: known techniques for this category (study these before "
            "inventing your own) ---\n" + tech
        )
    return system


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


def _custom(spec: dict[str, Any]) -> Built:
    """A real external target. The direction picks the toolset: web gets http + run_python,
    crypto/misc and forensics get run_python (pointed at a workspace when the user attached
    files). No known flag — any flag found is reported."""
    direction = spec.get("category", "web")
    description = spec.get("description", "")
    attachments = spec.get("attachments") or []
    urls = spec.get("urls") or ([spec["url"]] if spec.get("url") else [])

    workdir: Path | None = None
    attachment_block = ""
    if attachments:
        workdir = Path(tempfile.mkdtemp(prefix="ctf-custom-"))
        lines: list[str] = []
        for path_str in attachments:
            path = Path(path_str)
            name = path.name
            data = path.read_bytes()
            (workdir / name).write_bytes(data)
            entry = f"  - {name} ({len(data)} bytes)"
            # Inline small text files so source code is visible without a tool call.
            if len(data) <= 8192:
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = None
                if text is not None:
                    entry += "\n```\n" + text + "\n```"
            lines.append(entry)
        attachment_block = (
            "Attached files (also readable via run_python's working directory):\n"
            + "\n".join(lines) + "\n\n"
        )

    def cleanup_workdir() -> None:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)

    if direction == "web":
        web = importlib.import_module("web.agent")
        client = web.new_http_client()
        tools = web.web_tools_multi(urls, client, workdir)
        targets = "\n".join(f"[{i}] {u}" for i, u in enumerate(urls))
        user = (
            f"Targets:\n{targets}\n\n"
            f"{attachment_block}Challenge description: {description or '(none given)'}"
        )

        def cleanup() -> None:
            client.close()
            cleanup_workdir()

        return None, tools, _system_with_techniques(web.SYSTEM_PROMPT, "web"), user, cleanup

    if direction == "crypto":
        crypto = importlib.import_module("crypto.agent")
        tools = [python_tool(workdir)]
        user = f"{attachment_block}Challenge description: {description or '(none given)'}"
        return None, tools, _system_with_techniques(crypto.SYSTEM_PROMPT, "crypto"), user, cleanup_workdir

    if direction == "forensics":
        forensics = importlib.import_module("forensics.agent")
        if workdir is not None:
            tools = [python_tool(workdir)]
            system = forensics.WORKSPACE_SYSTEM_PROMPT
        else:
            tools = [python_tool()]
            system = forensics.SYSTEM_PROMPT
        user = f"{attachment_block}Challenge description: {description or '(none given)'}"
        return None, tools, _system_with_techniques(system, "forensics"), user, cleanup_workdir

    raise ValueError(f"unsupported custom direction: {direction}")


def build_task(spec: dict[str, Any]) -> Built:
    kind = spec.get("kind")
    if kind == "benchmark":
        return _benchmark(spec["category"], spec["name"])
    if kind == "custom":
        return _custom(spec)
    raise ValueError(f"unknown task kind: {kind}")
