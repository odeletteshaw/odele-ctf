"""CTF agent team configuration (RAFT-style: agents with roles/directions).

A team maps each challenge direction to the agent (token) that specializes in it, so
multiple agents work in parallel on different directions without colliding. The mapping
lives in the console database and is editable from the Team page. A legacy
~/.odele-ctf/team.json is imported once when the database has no team yet (the file is
left in place as a backup); DEFAULT_TEAM is the final fallback.
"""

import json
from pathlib import Path

from backend.settings import settings

LEGACY_PATH = Path.home() / ".odele-ctf" / "team.json"

DEFAULT_TEAM = [
    {"token_index": 0, "name": "odele", "directions": ["web"]},
    {"token_index": 1, "name": "odele-1", "directions": ["crypto", "misc"]},
    {"token_index": 2, "name": "odele-3", "directions": ["forensics", "reverse"]},
]


def _legacy_team() -> list[dict] | None:
    if not LEGACY_PATH.exists():
        return None
    try:
        members = json.loads(LEGACY_PATH.read_text()).get("members")
    except (OSError, ValueError):
        return None
    return members if isinstance(members, list) and members else None


def load_team() -> list[dict]:
    stored = settings.get("team")
    if isinstance(stored, list) and stored:
        return stored
    legacy = _legacy_team()
    if legacy:
        settings.set("team", legacy)  # migrate once
        return legacy
    return DEFAULT_TEAM


def save_team(members: list[dict]) -> None:
    settings.set("team", members)


def direction_to_token_index(team: list[dict]) -> dict[str, int]:
    """Map each direction to the token_index of the member that handles it."""
    mapping: dict[str, int] = {}
    for m in team:
        for d in m.get("directions", []):
            mapping[d] = m.get("token_index", 0)
    return mapping
