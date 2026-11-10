"""Crypto category: the agent breaks a cipher using run_python only. The challenge
data (ciphertext, keys, parameters) arrives as the prompt; there is no network target.
The model loop, provider config, and sandbox live in core/ and are shared.

Usage: python crypto/agent.py challenge.txt      (or pipe the challenge on stdin)
"""

import argparse
import sys
from pathlib import Path

# Make the repo root importable whether run as a script or from any directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import SolveResult, solve  # noqa: E402
from core.sandbox import python_tool  # noqa: E402

SYSTEM_PROMPT = """You are an expert at breaking cryptography in CTF challenges.
Your tool is run_python: write Python to analyze the scheme and compute the plaintext.
There is no network. Work in steps: identify the scheme, then break it.

Useful techniques:
- Brute force small keyspaces, e.g. all 256 keys of a single-byte XOR.
- Use known plaintext (the flag starts with 'flag{') to recover a repeating-key XOR.
- Peel nested encodings: base64, base32, hex, rot13.
- RSA: if e is small (e.g. 3) and the message is short, the ciphertext may be a perfect
  e-th power, so take the integer e-th root. If the modulus is small or its primes are
  close together, factor it (trial division or Fermat), then d = e^-1 mod phi(n).
- pycryptodome (Crypto.*), sympy, and hashlib are available in the sandbox. Reach for
  library routines rather than writing slow searches: sympy.discrete_log (fast when the
  group order is smooth), sympy.factorint, sympy.ntheory.residue_ntheory, etc.

The sandbox kills any run after ~15 seconds of CPU, so never brute-force a large space
by hand — pick the algorithm or library that makes the problem small first.

Flags look like flag{...}. Print the flag you recover and end your final message with
it on its own line."""


def solve_crypto(challenge_text: str, model: str | None = None, max_turns: int = 30) -> SolveResult:
    return solve([python_tool()], SYSTEM_PROMPT, challenge_text, model=model, max_turns=max_turns)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", nargs="?", help="File with the challenge text; stdin if omitted")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    text = Path(args.challenge).read_text() if args.challenge else sys.stdin.read()
    result = solve_crypto(text, args.model)
    print(f"\nflag: {result.flag}  tool calls: {result.tool_calls}")


if __name__ == "__main__":
    main()
