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
from tools.oracle import oracle_tool  # noqa: E402
from tools.sandbox import python_tool  # noqa: E402

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


ORACLE_SYSTEM_PROMPT = """You are breaking a crypto challenge that exposes an INTERACTIVE ORACLE.
Your tools:
- query_oracle: send a BATCH of inputs (hex) and get one answer per input (indexed). Batch
  many guesses per call — you have a bounded number of turns, so don't query one at a time.
- run_python: compute — build batches of ciphertexts, XOR intermediate bytes, binary-search.

The oracle leaks a bit of information per query. Classic patterns:
- Padding oracle (AES-CBC): the oracle says whether the decrypted PKCS7 padding is valid. For
  each byte, try all 256 values in ONE batch so the padding becomes valid, recover the
  intermediate byte (intermediate ^ guessed = pad), XOR with the previous block/IV to get the
  plaintext, and walk backward from the last block. A "valid" reply can be a FALSE POSITIVE (the
  real padding is longer than the pad length you're testing): after a valid guess, flip the next
  byte and re-query — if it stays valid, that guess was wrong; skip it and keep brute-forcing.
- RSA LSB oracle: the oracle reveals the low bit of m = c^d mod n. Batch-query c * 2^(i*e) mod n
  for i=1..bits; the replies are the binary digits of m/n, so reconstruct m = n * sum(b_i / 2^i)
  with integer arithmetic.
- ECB byte-at-a-time: the oracle returns the encryption of your chosen plaintext + a secret
  suffix. Align the secret to a block boundary with padding, then recover it one byte at a time
  by matching blocks.

Flags look like flag{...}. Print the flag and end your final message with it on its own line."""


def solve_crypto_oracle(oracle, challenge_text: str, model: str | None = None,
                        max_turns: int = 60) -> SolveResult:
    tool = oracle_tool(
        "query_oracle",
        "Query the target oracle with a batch of inputs (hex) and get one answer per input.",
        oracle.query,
        "ciphertext",
    )
    return solve([tool, python_tool()], ORACLE_SYSTEM_PROMPT, challenge_text,
                 model=model, max_turns=max_turns)


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
