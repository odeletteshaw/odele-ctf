"""Run the forensics agent against local challenges. Text challenges expose DESCRIPTION and
make(flag) -> str; large-artifact challenges expose make(flag) -> Workspace. See CLAUDE.md 出题规范.

Usage: python agent/categories/forensics/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agent.evaluate import benchmark  # noqa: E402
from agent.categories.forensics.agent import solve_forensics, solve_forensics_workspace  # noqa: E402
from agent.categories.forensics.challenges import gzip_nested, http_chunked, image_lsb, large_blob, magic_bytes, pcap_stream, polyglot, trailing_data, wav_lsb, zip_nested  # noqa: E402
from agent.categories.forensics.workspace import Workspace  # noqa: E402

CHALLENGES = {
    "trailing_data": trailing_data,
    "zip_nested": zip_nested,
    "pcap_stream": pcap_stream,
    "wav_lsb": wav_lsb,
    "large_blob": large_blob,
    "magic_bytes": magic_bytes,
    "gzip_nested": gzip_nested,
    "polyglot": polyglot,
    "image_lsb": image_lsb,
    "http_chunked": http_chunked,
}


def _make(module, flag):
    return module.make(flag)


def _solve(target, description, on_event=None):
    if isinstance(target, Workspace):
        return solve_forensics_workspace(target, description, on_event=on_event)
    return solve_forensics(target, on_event=on_event)


def _cleanup(target):
    if isinstance(target, Workspace):
        target.cleanup()


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve, cleanup=_cleanup)
