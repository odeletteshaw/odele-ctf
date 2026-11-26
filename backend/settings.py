"""Local configuration stored in the database and editable from the console.

Holds the CTF2 agent tokens, the direction -> agent team mapping, and the model/provider
settings (API base / model / key / timeout). Values here override `.env`; the database is
the source of truth once a field has been saved. The settings live in the same SQLite
file as sessions/memories (mode 0600), so keys and tokens never sit in the repo.

`apply_model_settings()` pushes the stored provider config into `agent.config` and the
process environment, so the solve loop and the worker subprocesses (spawned later, which
inherit the environment) all use it.
"""

import os
from pathlib import Path
from typing import Any

import agent.config as agent_config
from backend import db

MODEL_FIELDS = ("model", "api_base", "api_key", "api_timeout")
MAX_TOKENS = 16


def mask_secret(value: str) -> str:
    """Render a secret for display: sk-…abcd for API keys, …abcd otherwise."""
    if not value:
        return ""
    if len(value) <= 4:
        return "…"
    tail = value[-4:]
    return f"sk-…{tail}" if value.startswith("sk-") else f"…{tail}"


def _env_tokens() -> list[str]:
    """CTF2 tokens from the environment (CTF2_AGENT_TOKEN_0/1/2..., or the legacy
    CTF2_AGENT_TOKEN as a single fallback)."""
    tokens: list[str] = []
    for i in range(MAX_TOKENS):
        t = os.environ.get(f"CTF2_AGENT_TOKEN_{i}")
        if t:
            tokens.append(t)
        else:
            break
    if not tokens and os.environ.get("CTF2_AGENT_TOKEN"):
        tokens.append(os.environ["CTF2_AGENT_TOKEN"])
    return tokens


class Settings:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else db.DEFAULT_PATH
        self._conn = db.connect(self.path)

    # ---- generic -----------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return db.get_setting(self._conn, key, default)

    def set(self, key: str, value: Any) -> None:
        db.set_setting(self._conn, key, value)

    # ---- platform tokens ---------------------------------------------------
    def tokens(self) -> list[str]:
        """Stored tokens if any were saved; otherwise the .env/environment ones."""
        stored = self.get("ctf2_tokens")
        if isinstance(stored, list):
            return [t for t in stored if isinstance(t, str) and t.strip()]
        return _env_tokens()

    def token_hints(self) -> list[dict[str, Any]]:
        return [{"index": i, "hint": mask_secret(t)} for i, t in enumerate(self.tokens())]

    def add_token(self, token: str) -> None:
        token = token.strip()
        if not token:
            return
        tokens = self.tokens()
        if token not in tokens and len(tokens) < MAX_TOKENS:
            self.set("ctf2_tokens", tokens + [token])

    def remove_token(self, index: int) -> None:
        tokens = self.tokens()
        if 0 <= index < len(tokens):
            del tokens[index]
            self.set("ctf2_tokens", tokens)

    # ---- model / provider --------------------------------------------------
    def effective_api_key(self) -> str:
        return (self.get("api_key") or os.environ.get("CTF_API_KEY")
                or os.environ.get("DEEPSEEK_API_KEY") or "")

    def model_config(self) -> dict[str, Any]:
        return {
            "model": self.get("model") or agent_config.DEFAULT_MODEL,
            "api_base": self.get("api_base") or agent_config.API_BASE,
            "api_key": self.effective_api_key(),
            "api_timeout": self.get("api_timeout") or agent_config.API_TIMEOUT,
        }

    def update_model(self, changes: dict[str, Any]) -> None:
        for key in MODEL_FIELDS:
            value = changes.get(key)
            if value in (None, ""):
                continue
            if key == "api_timeout":
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
            self.set(key, str(value) if key != "api_timeout" else value)


def apply_model_settings(store: Settings) -> None:
    """Use the stored provider config in this process and in workers spawned from it."""
    cfg = store.model_config()
    os.environ["CTF_MODEL"] = str(cfg["model"])
    os.environ["CTF_API_BASE"] = str(cfg["api_base"])
    os.environ["CTF_API_TIMEOUT"] = str(cfg["api_timeout"])
    if cfg["api_key"]:
        os.environ["CTF_API_KEY"] = str(cfg["api_key"])
    agent_config.DEFAULT_MODEL = str(cfg["model"])
    agent_config.API_BASE = str(cfg["api_base"])
    agent_config.API_TIMEOUT = float(cfg["api_timeout"])
    agent_config.API_KEY = str(cfg["api_key"]) or None


settings = Settings()
