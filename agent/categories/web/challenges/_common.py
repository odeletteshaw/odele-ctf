"""Shared helpers for web challenge authors (JWT / base64url / bearer). The agent never
imports this — it is the authoring side, like _harness.py."""

import base64
import hashlib
import hmac
import json

from ._harness import Request


def b64u(raw: bytes) -> str:
    """URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def ub64u(value: str) -> bytes:
    """Inverse of b64u: restore padding, then decode."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_hs256(payload: dict, secret: bytes) -> str:
    """Sign a JWT payload with HS256."""
    header = b64u(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = b64u(json.dumps(payload).encode())
    signature = hmac.new(secret, f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{b64u(signature)}"


def bearer(req: Request) -> str:
    """Extract the token from the Authorization: Bearer header ("" if absent)."""
    auth = req.headers.get("Authorization", "") or ""
    return auth[len("Bearer ") :].strip() if auth.startswith("Bearer ") else ""
