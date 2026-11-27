"""Direction -> platform token slot mapping (打题 Token 槽位).

Separate from the role team: this only decides which CTF2 agent token a direction's
solve uses. Stored in the settings table; editable from the Token 槽位 page.
"""

from backend.settings import settings

DEFAULT_SLOTS = {
    "web": 0,
    "crypto": 1,
    "misc": 1,
    "forensics": 2,
    "reverse": 2,
    "pwn": 2,
    "ai": 2,
    "cloud": 2,
    "blockchain": 2,
    "ics": 2,
    "iot": 2,
    "ir": 2,
    "pentest": 2,
}


def load_slots() -> dict[str, int]:
    stored = settings.get("token_slots")
    slots = dict(DEFAULT_SLOTS)
    if isinstance(stored, dict):
        for direction, index in stored.items():
            try:
                slots[str(direction)] = int(index)
            except (TypeError, ValueError):
                continue
    return slots


def save_slots(mapping: dict) -> None:
    clean: dict[str, int] = {}
    for direction, index in (mapping or {}).items():
        try:
            clean[str(direction)] = max(0, int(index))
        except (TypeError, ValueError):
            continue
    settings.set("token_slots", clean)


def direction_to_token_index() -> dict[str, int]:
    return load_slots()
