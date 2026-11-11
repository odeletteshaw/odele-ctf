"""Run the forensics agent against local challenges. Text challenges expose DESCRIPTION and
make(flag) -> str; large-artifact challenges expose make(flag) -> Workspace. See TODO.md.

Usage: python forensics/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from forensics.agent import solve_forensics, solve_forensics_workspace  # noqa: E402
from forensics.challenges import gzip_nested, large_blob, magic_bytes, pcap_stream, trailing_data, wav_lsb, zip_nested  # noqa: E402
from forensics.workspace import Workspace  # noqa: E402

CHALLENGES = {
    "trailing_data": trailing_data,
    "zip_nested": zip_nested,
    "pcap_stream": pcap_stream,
    "wav_lsb": wav_lsb,
    "large_blob": large_blob,
    "magic_bytes": magic_bytes,
    "gzip_nested": gzip_nested,
}


def _make(module, flag):
    return module.make(flag)


def _solve(target, description):
    if isinstance(target, Workspace):
        return solve_forensics_workspace(target, description)
    return solve_forensics(target)


def _cleanup(target):
    if isinstance(target, Workspace):
        target.cleanup()


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve, cleanup=_cleanup)
