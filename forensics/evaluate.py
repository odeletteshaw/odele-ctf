"""Run the forensics agent against local challenges. Each module exposes DESCRIPTION and
make(flag) -> str (challenge text with the artifact embedded as base64). See TODO.md.

Usage: python forensics/evaluate.py [name ...]
"""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forensics.agent import solve_forensics  # noqa: E402
from forensics.challenges import pcap_stream, trailing_data, wav_lsb, zip_nested  # noqa: E402

CHALLENGES: dict = {
    "trailing_data": trailing_data,
    "zip_nested": zip_nested,
    "pcap_stream": pcap_stream,
    "wav_lsb": wav_lsb,
}


def main(names: list[str]) -> None:
    selected = names or list(CHALLENGES)
    solved = 0
    for name in selected:
        flag = f"flag{{{secrets.token_hex(12)}}}"
        result = solve_forensics(CHALLENGES[name].make(flag))
        passed = result.flag == flag
        solved += passed
        print(f"{'PASS' if passed else 'FAIL'} {name} ({result.tool_calls} run_python calls)")
    print(f"\nSolved {solved}/{len(selected)}")


if __name__ == "__main__":
    main(sys.argv[1:])
