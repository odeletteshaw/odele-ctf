"""Run the forensics agent against local challenges. Each module exposes DESCRIPTION and
make(flag) -> str (challenge text with the artifact embedded as base64). See TODO.md.

Usage: python forensics/evaluate.py [name ...]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluate import benchmark  # noqa: E402
from forensics.agent import solve_forensics  # noqa: E402
from forensics.challenges import pcap_stream, trailing_data, wav_lsb, zip_nested  # noqa: E402

CHALLENGES = {
    "trailing_data": trailing_data,
    "zip_nested": zip_nested,
    "pcap_stream": pcap_stream,
    "wav_lsb": wav_lsb,
}


def _make(module, flag):
    return module.make(flag)


def _solve(text, _description):
    return solve_forensics(text)


if __name__ == "__main__":
    benchmark(CHALLENGES, sys.argv[1:], make=_make, solve=_solve)
