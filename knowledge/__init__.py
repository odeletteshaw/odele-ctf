"""Knowledge base: reusable CTF techniques keyed by category.

`load_techniques(category)` concatenates the markdown cards under
`knowledge/techniques/<category>/` so the agent's system prompt can carry them at
solve time (retrieval is a simple "all cards for this category" for now)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_techniques(category: str) -> str:
    folder = ROOT / "techniques" / category
    if not folder.is_dir():
        return ""
    cards: list[str] = []
    for path in sorted(folder.glob("*.md")):
        text = path.read_text().strip()
        if text:
            cards.append(text)
    return "\n\n".join(cards)
