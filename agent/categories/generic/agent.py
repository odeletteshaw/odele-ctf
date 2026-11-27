"""Generic security direction (cloud / blockchain / IoT / ICS / IR / pentest).

These directions have role experts and skill packs, but no hermetic benchmark of
their own. For custom targets the expert gets the web-style toolkit (HTTP, raw
downloads, run_python, knowledge) and a direction-neutral security prompt; when no
URL is attached it falls back to text/computation only.
"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent.loop import SolveResult, Tool, solve  # noqa: E402
from agent.tools.http import (  # noqa: E402
    download_tool,
    multi_http_batch_tool,
    multi_http_tool,
    new_http_client,
)
from agent.tools.knowledge import knowledge_tool  # noqa: E402
from agent.tools.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are an expert security engineer solving a CTF challenge in the
{direction} domain. Work evidence-first: map the target, form one hypothesis at a time,
and back every conclusion with a request/response, a file offset, or a decoded value.

Tools (when the task has a target URL): http_request / http_batch to map and probe,
download_file to save raw artifacts, run_python to compute, decode, brute-force or parse,
and search_knowledge for technique cards. Without a target, use run_python on the provided
material. If a parameter has no visible effect, look for the real handler rather than
re-sending the same request. Stop as soon as a response contains the flag, and copy it
verbatim.

Flags look like flag{{...}}. Only report a flag you actually observed, and end your final
message with it on its own line."""


def system_prompt(direction: str) -> str:
    return SYSTEM_PROMPT.format(direction=direction)


def target_tools(urls: list[str], client, workdir: Path) -> list[Tool]:
    return [multi_http_tool(urls, client), multi_http_batch_tool(urls, client),
            download_tool(urls, client, workdir), python_tool(workdir), knowledge_tool("web")]


def text_tools(workdir: Path) -> list[Tool]:
    return [python_tool(workdir), knowledge_tool("web")]


def solve_generic(direction: str, description: str, urls: list[str] | None = None,
                  model: str | None = None, max_turns: int = 100) -> SolveResult:
    workdir = Path(tempfile.mkdtemp(prefix="ctf-generic-"))
    client = new_http_client() if urls else None
    try:
        tools = target_tools(urls, client, workdir) if client else text_tools(workdir)
        return solve(tools, system_prompt(direction), description, model=model,
                     max_turns=max_turns)
    finally:
        if client:
            client.close()
        shutil.rmtree(workdir, ignore_errors=True)
