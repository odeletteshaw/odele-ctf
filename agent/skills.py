"""Flat skill library shared by every team role.

Layout: `agent/skill_library/*.md`, one file per skill, with frontmatter:

    ---
    id: web-sql-injection
    name: SQL注入
    description: ...
    tags: [hello-ctf, web]
    ---

Roles bind skills by id or by tag selector (`tag:web`); `*` selects everything.
The library is flat — there are no per-role pack directories.
"""

import re
from pathlib import Path
from typing import Any

from agent.loop import Tool

ROOT = Path(__file__).resolve().parent
LIBRARY = ROOT / "skill_library"
MAX_INDEX_CHARS = 3000
SKIP_FILES = {"NOTICE.md"}

_CACHE: dict[str, Any] = {"stamp": None, "entries": []}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta: dict[str, Any] = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "tags":
            value = value.strip("[]")
            meta["tags"] = [t.strip() for t in value.split(",") if t.strip()]
        else:
            meta[key] = value
    return meta, text[end + 4:].lstrip("\n")


def read(entry: dict[str, Any]) -> str:
    _, body = _parse_frontmatter(entry["path"].read_text(errors="replace"))
    return body


def _stamp() -> float:
    if not LIBRARY.is_dir():
        return 0.0
    return max((p.stat().st_mtime for p in LIBRARY.glob("*.md")), default=0.0)


def entries() -> list[dict[str, Any]]:
    """All skills in the library (frontmatter parsed; cached by directory mtime)."""
    stamp = _stamp()
    if _CACHE["stamp"] == stamp and _CACHE["entries"]:
        return _CACHE["entries"]
    found: list[dict[str, Any]] = []
    if LIBRARY.is_dir():
        for path in sorted(LIBRARY.glob("*.md")):
            if path.name in SKIP_FILES:
                continue
            meta, body = _parse_frontmatter(path.read_text(errors="replace"))
            skill_id = str(meta.get("id") or path.stem)
            name = str(meta.get("name") or path.stem)
            description = str(meta.get("description") or "")
            if not description:
                for line in body.splitlines():
                    s = line.strip()
                    if s and not s.startswith(("#", ">", "|", "-")):
                        description = s[:160]
                        break
            tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
            found.append({
                "id": skill_id,
                "name": name,
                "description": description,
                "tags": tags,
                "kind": "method" if "method" in tags else "reference",
                "path": path,
            })
    _CACHE.update(stamp=stamp, entries=found)
    return found


def resolve(selectors: list[str] | None) -> list[dict[str, Any]]:
    """Resolve ids / tag:<tag> / * to skill entries (deduped, library order)."""
    if not selectors:
        return []
    wanted_ids: set[str] = set()
    wanted_tags: set[str] = set()
    everything = False
    for raw in selectors:
        selector = str(raw).strip()
        if not selector:
            continue
        if selector == "*":
            everything = True
        elif selector.startswith("tag:"):
            wanted_tags.add(selector[4:].strip())
        else:
            wanted_ids.add(selector)
    picked = []
    for entry in entries():
        if everything or entry["id"] in wanted_ids or any(t in entry["tags"] for t in wanted_tags):
            picked.append(entry)
    return picked


def index(items: list[dict[str, Any]]) -> str:
    lines = [f"- {e['name']}（{e['id']}）：{e['description']}" for e in items]
    text = "\n".join(lines)
    if len(text) > MAX_INDEX_CHARS:
        text = text[:MAX_INDEX_CHARS] + "\n…（索引已截断，用检索读取）"
    return text


def search(items: list[dict[str, Any]], query: str, limit: int = 3,
           max_chars: int = 6000) -> str:
    q = query.strip().lower()
    if not q:
        return ""
    tokens = [t for t in re.split(r"[^\w]+", q) if len(t) >= 2]
    compact = q.replace(" ", "")
    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in items:
        body = read(entry)
        low = body.lower()
        name = str(entry["name"]).lower()
        name_compact = name.replace(" ", "")
        score = 0
        if compact and compact in low.replace(" ", ""):
            score += 20
        if compact and name_compact == compact:
            score += 30
        elif compact and compact in name_compact:
            score += 8
        for token in tokens:
            if token in name:
                score += 5
            if token in low:
                score += 1
        if score:
            scored.append((score, entry))
    if not scored:
        return ""
    scored.sort(key=lambda pair: -pair[0])
    parts: list[str] = []
    for _, entry in scored[:limit]:
        body = read(entry)[:max(600, max_chars // max(1, min(limit, len(scored))))]
        parts.append(f"## {entry['name']}\n{body}")
    return "\n\n---\n\n".join(parts)


def briefing(items: list[dict[str, Any]], max_chars: int = 4000) -> str:
    parts: list[str] = []
    idx = index(items)
    if idx:
        parts.append(idx)
    budget = max_chars - len(idx)
    for entry in items:
        if entry["kind"] != "method" or budget <= 0:
            continue
        body = read(entry)[:max(400, budget)]
        parts.append(f"\n### {entry['name']}\n{body}")
        budget -= len(body)
    return "\n".join(parts)


def role_skill_tool(items: list[dict[str, Any]]) -> Tool | None:
    if not items:
        return None

    def handler(args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "Error: 'query' is required"
        found = search(items, query)
        if not found:
            return f"No skill matches {query!r}. Try a broader keyword."
        return "\n" + found + "\n"

    return Tool(
        name="search_role_skill",
        description=(
            "Search the skills bound to YOUR role in the shared flat skill library "
            "(methods, checklists, imported reference material) and return matching text."
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


def available() -> list[dict[str, Any]]:
    """Library listing for the UI (no body)."""
    return [{"id": e["id"], "name": e["name"], "description": e["description"],
             "tags": e["tags"], "kind": e["kind"]} for e in entries()]


def tags() -> list[str]:
    found: set[str] = set()
    for entry in entries():
        found.update(entry["tags"])
    return sorted(found)


def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(items), "names": [e["name"] for e in items]}
