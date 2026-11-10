"""Single source of truth for the challenge categories (directions). Drives the GUI's
direction options and documents each category's status and the agent tool it needs.
"status" is "ready" when the category has a working agent + challenges, else "planned".
See ROADMAP.md for the sub-directions under each.
"""

CATEGORIES: dict[str, dict[str, str]] = {
    "web": {"label": "Web", "status": "ready", "tool": "http_request + run_python"},
    "crypto": {"label": "Crypto", "status": "ready", "tool": "run_python"},
    "misc": {"label": "Misc", "status": "ready", "tool": "run_python"},
    "pwn": {"label": "Pwn", "status": "ready", "tool": "send_input + run_python"},
    "reverse": {"label": "Reverse", "status": "planned", "tool": "disassembler + angr"},
    "forensics": {"label": "Forensics", "status": "ready", "tool": "run_python"},
    "ai": {"label": "AI", "status": "ready", "tool": "send_message + run_python"},
}


def ready_categories() -> list[str]:
    return [k for k, v in CATEGORIES.items() if v["status"] == "ready"]
