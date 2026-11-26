"""Knowledge base: reusable CTF techniques keyed by category.

`load_techniques(category)` returns a COMPACT index (title + one-liner) for the
system prompt, so the prompt stays small regardless of how many cards exist.
`search_techniques(category, query)` returns the full text of matching cards for
on-demand retrieval via the search_knowledge tool."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _cards(category: str) -> list[str]:
    folder = ROOT / "techniques" / category
    if not folder.is_dir():
        return []
    return [p.read_text().strip() for p in sorted(folder.glob("*.md"))]


def load_techniques(category: str) -> str:
    """Compact index (title + one-liner) of the category's techniques."""
    lines: list[str] = []
    for text in _cards(category):
        title = ""
        oneliner: list[str] = []
        in_oneliner = False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("# "):
                title = s[2:]
            elif s.startswith("**一句话**"):
                in_oneliner = True
                oneliner.append(s[len("**一句话**"):].strip(" ：:"))
            elif in_oneliner:
                if s.startswith("##"):
                    break  # end of the one-liner paragraph
                if s:
                    oneliner.append(s)
        if title:
            lines.append(f"- {title}：{' '.join(oneliner)}")
    return "\n".join(lines)


def search_techniques(category: str, query: str) -> list[str]:
    """Return the full text of cards whose content matches the query (case-insensitive)."""
    q = query.lower().strip()
    if not q:
        return []
    return [text for text in _cards(category) if q in text.lower()]


def search_memories(query: str, limit: int = 5) -> list[dict]:
    """Search the accumulated memory pool (auto-saved solve writeups) by keyword."""
    q = query.lower().strip()
    if not q:
        return []
    db = Path.home() / ".odele-ctf" / "sessions.db"
    if not db.exists():
        return []
    import sqlite3
    try:
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT category, title, content, source, created_at FROM memories "
            "WHERE lower(title || ' ' || content) LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{q}%", limit),
        ).fetchall()
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [{"category": r[0], "title": r[1], "content": r[2],
             "source": r[3], "created_at": r[4]} for r in rows]
