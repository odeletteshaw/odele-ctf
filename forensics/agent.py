"""Forensics category — NOT YET IMPLEMENTED.

Blocked on a new agent tool. The agent needs read access to a provided artifact (image,
pcap, disk/memory dump, document) plus analysis helpers (binwalk / exiftool / strings /
tshark and Python libs like PIL / scapy). Once a file-analysis tool exists, implement
solve_forensics() like web/crypto. See ROADMAP.md and TODO.md.
"""

SYSTEM_PROMPT = """You are solving a forensics CTF challenge.
You can inspect the provided file and run Python (PIL, scapy available) plus analysis
tools. Carve data, read metadata, extract hidden content (steganography), or parse a
capture to recover the flag.
Flags look like flag{...}. End your final message with the flag on its own line."""

# TODO: build tools/files.py (scoped read of the artifact) + analysis helpers, then
#       def solve_forensics(artifact_path, description, ...) -> SolveResult.
