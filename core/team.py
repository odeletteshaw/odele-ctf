"""CTF agent team configuration (RAFT-style: agents with roles/directions).

A team maps each challenge direction to the agent (token) that specializes in it,
so multiple agents work in parallel on different directions without colliding.
Stored as JSON at ~/.odele-ctf/team.json; falls back to a default when absent.
"""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".odele-ctf" / "team.json"

DEFAULT_TEAM = [
    {"token_index": 0, "name": "odele", "directions": ["web"]},
    {"token_index": 1, "name": "odele-1", "directions": ["crypto", "misc"]},
    {"token_index": 2, "name": "odele-3", "directions": ["forensics", "reverse"]},
]


def load_team() -> list[dict]:
    if CONFIG_PATH.exists():
        try:
            members = json.loads(CONFIG_PATH.read_text()).get("members")
            if isinstance(members, list) and members:
                return members
        except Exception:
            pass
    return DEFAULT_TEAM


def save_team(members: list[dict]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"members": members}, ensure_ascii=False, indent=2))


def direction_to_token_index(team: list[dict]) -> dict[str, int]:
    """Map each direction to the token_index of the member that handles it."""
    mapping: dict[str, int] = {}
    for m in team:
        for d in m.get("directions", []):
            mapping[d] = m.get("token_index", 0)
    return mapping
