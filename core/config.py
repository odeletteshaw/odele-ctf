"""Shared model/provider configuration for every challenge category.

DeepSeek is the default because its credits are cheap for debugging. Any
OpenAI-compatible provider works by setting CTF_API_BASE / CTF_MODEL / CTF_API_KEY.
Real environment variables win over .env, so a one-off `CTF_MODEL=... python ...`
overrides the file without editing it.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    try:
        text = path.read_text()
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # setdefault: a real environment variable takes precedence over .env.
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")

API_BASE = os.environ.get("CTF_API_BASE", "https://api.deepseek.com")
API_KEY = os.environ.get("CTF_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
DEFAULT_MODEL = os.environ.get("CTF_MODEL", "deepseek-chat")
