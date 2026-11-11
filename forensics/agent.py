"""Forensics category: the agent is handed an artifact (a file) encoded as base64 in the
challenge text and must carve, parse, or extract the flag from it with run_python. Framing
the file as embedded base64 keeps the category hermetic and text-in — same shape as crypto
and misc, no new agent tool — while still exercising real forensic skills (file carving,
archive spelunking, packet reassembly, LSB stego). The agent writes its own analysis code;
run_python has the stdlib (struct, zlib, zipfile, wave, ...).

Challenge interface: each module in forensics/challenges/ exposes DESCRIPTION and
make(flag) -> str (the challenge text, with the artifact embedded as base64).

Usage: python forensics/agent.py challenge.txt   (or pipe the challenge on stdin)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import SolveResult, solve  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are solving a digital-forensics CTF challenge. The challenge text
embeds an artifact (a file) as base64. Your tool is run_python: decode the base64 to bytes
and analyze them. There is no network.

Think like a forensic analyst: identify the file type from its magic bytes; a file is often
longer than it looks, so check for data appended after the logical end; archives can hide
data in comments or nested layers; packet captures (pcap) need their records parsed and
streams reassembled; stego hides bits in the low bits of image/audio samples. The stdlib
has what you need (struct, zlib, zipfile, wave, gzip, tarfile), plus Pillow (PIL.Image) for
images.

Flags look like flag{...}. Print the flag and end your final message with it on its own line."""

WORKSPACE_SYSTEM_PROMPT = """You are solving a digital-forensics CTF challenge. The artifact
is one or more files already present in your working directory (run_python's cwd). Use
os.listdir('.') to see them, then open()/read() to analyze them — they persist across
run_python calls, so read them from disk each time rather than re-pasting their contents.
There is no network.

Think like a forensic analyst: identify file types from magic bytes; a file is often longer
than it looks, so check for data appended after the logical end; archives hide data in
comments or nested layers; packet captures need record parsing and stream reassembly; stego
hides bits in the low bits of samples; data may be XORed or encoded. The stdlib has what you
need (struct, zlib, zipfile, wave, gzip, tarfile), plus Pillow (PIL.Image) for images.

Flags look like flag{...}. Print the flag and end your final message with it on its own line."""


def solve_forensics(challenge_text: str, model: str | None = None,
                    max_turns: int = 30) -> SolveResult:
    return solve([python_tool()], SYSTEM_PROMPT, challenge_text, model=model, max_turns=max_turns)


def solve_forensics_workspace(ws, description: str, model: str | None = None,
                              max_turns: int = 30) -> SolveResult:
    return solve([python_tool(ws.dir)], WORKSPACE_SYSTEM_PROMPT, description,
                 model=model, max_turns=max_turns)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", nargs="?")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    text = Path(args.challenge).read_text() if args.challenge else sys.stdin.read()
    result = solve_forensics(text, args.model)
    print(f"\nflag: {result.flag}  tool calls: {result.tool_calls}")


if __name__ == "__main__":
    main()
