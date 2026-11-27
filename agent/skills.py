"""Per-role skill packages.

Layout (all committed to the repo):

    agent/team_skills/lead/SKILL.md
    agent/team_skills/recon/SKILL.md
    agent/team_skills/reporter/SKILL.md
    agent/team_skills/experts/_common/SKILL.md
    agent/team_skills/experts/<direction>/SKILL.md
    .../references/*.md          # imported long-form material

A role's system prompt gets a compact index (titles + one-liners) and a
`search_role_skill` tool reads the matching text on demand, so big material sets do
not bloat the prompt. Lead and reporter cannot call tools, so they get a short
briefing (index + SKILL.md body) appended to their prompt instead.
"""

import re
from pathlib import Path
from typing import Any

from agent.loop import Tool

ROOT = Path(__file__).resolve().parent / "team_skills"
MAX_INDEX_CHARS = 3000


def skill_dirs(role: str, category: str | None = None) -> list[Path]:
    """Existing skill directories for a role.

    Every role also gets the shared pack (routing / taxonomy / cross-cutting methods);
    experts merge that with the common expert pack and their direction pack.
    """
    candidates = [ROOT / "_shared"]
    if role == "expert":
        candidates.append(ROOT / "experts" / "_common")
        if category:
            candidates.append(ROOT / "experts" / category)
    else:
        candidates.append(ROOT / role)
    return [d for d in candidates if d.is_dir()]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    key = None
    for line in text[3:end].splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s", line) and key:
            meta[key] = (meta[key] + " " + line.strip()).strip()
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            meta[key] = value.strip().lstrip(">|").strip()
    return meta, text[end + 4:].lstrip("\n")


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _oneliner(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("**一句话**"):
            return s[len("**一句话**"):].strip(" ：:")
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("---"):
            return s[:160]
    return ""


def entries(dirs: list[Path]) -> list[dict[str, Any]]:
    """Flatten a role's skill dirs into index entries."""
    found: list[dict[str, Any]] = []
    for folder in dirs:
        skill_md = folder / "SKILL.md"
        if skill_md.is_file():
            text = skill_md.read_text(errors="replace")
            meta, body = _parse_frontmatter(text)
            found.append({
                "name": meta.get("name") or _title(body, folder.name),
                "description": meta.get("description") or _oneliner(body),
                "path": skill_md,
                "kind": "skill",
            })
        for ref in sorted((folder / "references").glob("*.md")) if (folder / "references").is_dir() else []:
            text = ref.read_text(errors="replace")
            meta, body = _parse_frontmatter(text)
            found.append({
                "name": meta.get("name") or _title(body, ref.stem),
                "description": meta.get("description") or _oneliner(body),
                "path": ref,
                "kind": "reference",
            })
    return found


def index(dirs: list[Path]) -> str:
    """Compact index for a system prompt."""
    lines: list[str] = []
    for entry in entries(dirs):
        prefix = "-" if entry["kind"] == "skill" else "  ·"
        desc = f"：{entry['description']}" if entry["description"] else ""
        lines.append(f"{prefix} {entry['name']}{desc}")
    text = "\n".join(lines)
    if len(text) > MAX_INDEX_CHARS:
        text = text[:MAX_INDEX_CHARS] + "\n…（索引已截断，用检索读取）"
    return text


def search(dirs: list[Path], query: str, limit: int = 3, max_chars: int = 6000) -> str:
    """Keyword search across the role's skills/references; returns matching text."""
    q = query.strip().lower()
    if not q:
        return ""
    tokens = [t for t in re.split(r"[^\w]+", q) if len(t) >= 2]
    compact = q.replace(" ", "")
    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in entries(dirs):
        text = entry["path"].read_text(errors="replace")
        _, body = _parse_frontmatter(text)
        low = body.lower()
        name = str(entry.get("name", "")).lower()
        name_compact = name.replace(" ", "")
        score = 0
        if compact and compact in low.replace(" ", ""):
            score += 20
        if compact and name_compact == compact:
            score += 30  # explicit title match beats a broader page that merely mentions it
        elif compact and compact in name_compact:
            score += 8
        for token in tokens:
            if token in name:  # title match is a much stronger signal
                score += 5
            if token in low:
                score += 1
        if score:
            scored.append((score, {**entry, "text": text}))
    if not scored:
        return ""
    scored.sort(key=lambda pair: -pair[0])
    parts: list[str] = []
    budget = max_chars
    for _, entry in scored[:limit]:
        _, body = _parse_frontmatter(entry["text"])
        take = min(len(body), max(600, budget // max(1, min(limit, len(scored)))))
        body = body[:take]
        parts.append(f"## {entry['name']}\n{body}")
        budget -= len(body)
        if budget <= 0:
            break
    return "\n\n---\n\n".join(parts)


def briefing(dirs: list[Path], max_chars: int = 4000) -> str:
    """Index + SKILL.md bodies, for roles that cannot call tools."""
    parts: list[str] = []
    idx = index(dirs)
    if idx:
        parts.append(idx)
    budget = max_chars - len(idx)
    for entry in entries(dirs):
        if entry["kind"] != "skill" or budget <= 0:
            continue
        text = entry["path"].read_text(errors="replace")
        _, body = _parse_frontmatter(text)
        take = body[:max(400, budget)]
        parts.append(f"\n### {entry['name']}\n{take}")
        budget -= len(take)
    return "\n".join(parts)


def role_skill_tool(dirs: list[Path]) -> Tool | None:
    """The search_role_skill capability for a role (None when it has no skills)."""
    if not entries(dirs):
        return None

    def handler(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required"
        found = search(dirs, query)
        if not found:
            return f"No role skill matches {query!r}. Try a broader keyword."
        return "\n" + found + "\n"

    return Tool(
        name="search_role_skill",
        description=(
            "Search YOUR role's skill pack (methods, checklists and imported reference "
            "material) by keyword and return the matching text. Use it before acting on "
            "a class of task, or when you need the team's standard procedure."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Keywords, e.g. 'SQL 注入', '报告模板', 'recon checklist'"},
            },
            "required": ["query"],
        },
        handler=handler,
    )


def summary(dirs: list[Path]) -> dict[str, Any]:
    items = entries(dirs)
    return {
        "count": len(items),
        "names": [e["name"] for e in items],
    }
