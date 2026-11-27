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

from agent.loop import Tool  # noqa: E402
from agent.knowledge import load_techniques  # noqa: E402
from agent.tools.sandbox import python_tool  # noqa: E402

Built = tuple[str | None, list[Tool], str, str, Callable[[], None]]

# Directions with role experts/skill packs but no dedicated hermetic category.
EXTRA_DIRECTIONS = {"cloud", "blockchain", "ics", "iot", "ir", "pentest"}


def _system_with_techniques(system: str, category: str) -> str:
    """Append a compact index of the category's techniques to the system prompt."""
    tech = load_techniques(category)
    if tech:
        return system + (
            "\n\n--- Technique index (search_knowledge to expand a specific one) ---\n" + tech
        )
    return system


def _benchmark(category: str, name: str) -> Built:
    flag = f"flag{{{secrets.token_hex(12)}}}"
    challenge = importlib.import_module(f"agent.categories.{category}.challenges.{name}")
    agent = importlib.import_module(f"agent.categories.{category}.agent")
    if category == "web":
        server, url = challenge.start(flag)
        client = agent.new_http_client()
        workdir = Path(tempfile.mkdtemp(prefix="ctf-web-"))
        tools = agent.web_tools(url, client, workdir)
        user = f"Target: {url}\n\nChallenge description: {challenge.DESCRIPTION}"

        def cleanup() -> None:
            server.shutdown()
            client.close()
            shutil.rmtree(workdir, ignore_errors=True)

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
        return flag, tools, _system_with_techniques(agent.SYSTEM_PROMPT, "reverse"), \
            challenge.DESCRIPTION, target.cleanup
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
        web = importlib.import_module("agent.categories.web.agent")
        client = web.new_http_client()
        if workdir is None:
            # web always gets a workspace so download_file can save raw bytes into it
            workdir = Path(tempfile.mkdtemp(prefix="ctf-custom-"))
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

    if direction in ("crypto", "misc"):  # text-in, run_python-only categories
        agent = importlib.import_module(f"agent.categories.{direction}.agent")
        tools = [python_tool(workdir)]
        user = f"{attachment_block}Challenge description: {description or '(none given)'}"
        return None, tools, _system_with_techniques(agent.SYSTEM_PROMPT, direction), \
            user, cleanup_workdir

    if direction in EXTRA_DIRECTIONS:
        generic = importlib.import_module("agent.categories.generic.agent")
        if urls and workdir is None:
            workdir = Path(tempfile.mkdtemp(prefix="ctf-custom-"))
        client = generic.new_http_client() if urls else None
        tools = (generic.target_tools(urls, client, workdir) if client
                 else generic.text_tools(workdir))
        user = f"{attachment_block}Challenge description: {description or '(none given)'}"

        def cleanup_extra() -> None:
            if client:
                client.close()
            cleanup_workdir()

        return None, tools, generic.system_prompt(direction), user, cleanup_extra

    if direction == "forensics":
        forensics = importlib.import_module("agent.categories.forensics.agent")
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
