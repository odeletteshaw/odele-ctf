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

import math
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


# Hello-CTF cards were imported flat from a nested doc tree, so their relative
# "[信息搜集](info-gathering.md)" / "[WEB](../web/index.md)" links point at paths that do
# not exist in the flat library — and the agent has no path-open tool anyway (only
# search_role_skill by keyword). Flatten such dead local links to their anchor text (a
# topic the agent can search for if it wants more); keep real external URLs clickable.
_LOCAL_MD_LINK = re.compile(r"\[([^\]]+)\]\((?!https?://)[^)]*\)")


def _flatten_dead_links(text: str) -> str:
    return _LOCAL_MD_LINK.sub(r"\1", text)


def read(entry: dict[str, Any]) -> str:
    _, body = _parse_frontmatter(entry["path"].read_text(errors="replace"))
    return _flatten_dead_links(body)


# Cards are filed by kind into subdirectories: methods/ (role playbooks = skills),
# reference/ (imported technique references), harvested/ (knowledge accrued from our own
# solves). The folder, not a tag, decides the kind.
_KIND_BY_DIR = {"methods": "method", "reference": "reference", "harvested": "harvested"}


def _stamp() -> float:
    if not LIBRARY.is_dir():
        return 0.0
    return max((p.stat().st_mtime for p in LIBRARY.rglob("*.md")), default=0.0)


def entries() -> list[dict[str, Any]]:
    """All skills in the library (frontmatter parsed; cached by directory mtime)."""
    stamp = _stamp()
    if _CACHE["stamp"] == stamp and _CACHE["entries"]:
        return _CACHE["entries"]
    found: list[dict[str, Any]] = []
    if LIBRARY.is_dir():
        for path in sorted(LIBRARY.rglob("*.md")):
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
            # Kind comes from the subfolder; fall back to the old tag heuristic for a
            # card still sitting at the library root.
            rel = path.relative_to(LIBRARY)
            kind = _KIND_BY_DIR.get(rel.parts[0] if len(rel.parts) > 1 else "",
                                    "method" if "method" in tags else "reference")
            found.append({
                "id": skill_id,
                "name": name,
                "description": description,
                "tags": tags,
                "kind": kind,
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


def _tokenize(text: str) -> list[str]:
    # \w is Unicode-aware, so a CJK phrase like "模板注入" stays one distinctive token
    # while "SQL injection" splits into two.
    return [t for t in re.split(r"[^\w]+", text.lower()) if len(t) >= 2]


_ASCII_TOKEN = re.compile(r"[a-z0-9_]+")


def _contains(token: str, text: str) -> bool:
    """Whether `text` contains `token`. ASCII tokens match on word boundaries so "sql"
    does not hit "nosql"; CJK tokens fall back to substring, because run-on Chinese
    prose ("不同于模板注入的") has no separators to tokenize on."""
    if _ASCII_TOKEN.fullmatch(token):
        return re.search(rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])", text) is not None
    return token in text


# Keep only results close to the best one: a long query always grazes a few cards on a
# stray token, and those trailing matches are noise, not coverage.
_REL_THRESHOLD = 0.3


def _is_generic(df: int, n: int) -> bool:
    """A token is too generic to be a topic signal when it appears in at least half the
    cards (and at least two of them) — e.g. "python"/"web" across a web role's skills.
    df-ratio, not a fixed idf floor, because a tiny corpus can't produce large idf even
    for a card's own distinctive name token (N=1 → idf=log 2)."""
    return df >= max(2, (n + 1) // 2)


def _corpus_df(items: list[dict[str, Any]]) -> tuple[dict[str, int], int]:
    """Document frequency of each token across the bound skills, for idf weighting."""
    df: dict[str, int] = {}
    for entry in items:
        present = set(_tokenize(str(entry["name"]))) | set(_tokenize(str(entry["description"])))
        present.update(t.lower() for t in entry["tags"])
        present.update(_tokenize(read(entry)))
        for token in present:
            df[token] = df.get(token, 0) + 1
    return df, len(items)


def search(items: list[dict[str, Any]], query: str, limit: int = 3,
           max_chars: int = 6000) -> str:
    """Rank the role's skills against `query` by idf-weighted field matches.

    Scoring rewards the curated fields (name, tags, description) over body prose and
    discounts tokens that appear in most cards (idf), so a query's rare, on-topic terms
    decide the ranking. A result is returned only when at least one query token hits a
    curated field with real idf — a match built purely from generic body words (e.g. an
    SSTI query grazing "python" inside a JS-deobfuscation card) scores nothing.
    """
    q = query.strip().lower()
    if not q:
        return ""
    q_tokens = list(dict.fromkeys(_tokenize(q)))
    if not q_tokens:
        return ""
    df, n = _corpus_df(items)

    def idf(token: str) -> float:
        d = df.get(token, 0)
        return math.log(1 + n / d) if d else 0.0

    compact = q.replace(" ", "")
    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in items:
        name = str(entry["name"]).lower()
        description = str(entry["description"]).lower()
        tagtext = " ".join(entry["tags"]).lower()
        body = read(entry).lower()
        score = 0.0
        strong = False
        if compact and compact == name.replace(" ", ""):
            score += 50.0
            strong = True
        for token in q_tokens:
            weight = idf(token)
            topical = not _is_generic(df.get(token, 0), n)
            if _contains(token, name) or _contains(token, tagtext):
                score += 6.0 * weight
            elif _contains(token, description):
                score += 3.0 * weight
            elif _contains(token, body):
                score += 1.0 * weight  # weaker, but a rare term here still signals coverage
            else:
                continue
            # A hit qualifies the result only when the token is distinctive. Generic words
            # ("python"/"web", in half the cards) never qualify, wherever they land — that
            # is what stopped the SSTI query from dragging up a JS-deobfuscation card. A
            # rare term qualifies even from the body, so coverage buried in prose surfaces.
            strong = strong or topical
        if score > 0 and strong:
            scored.append((score, entry))
    if not scored:
        return ""
    scored.sort(key=lambda pair: -pair[0])
    cutoff = scored[0][0] * _REL_THRESHOLD
    kept = [entry for score, entry in scored if score >= cutoff][:limit]
    parts: list[str] = []
    for entry in kept:
        body = read(entry)[:max(600, max_chars // max(1, len(kept)))]
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
        from agent.tools.knowledge import redact_flags
        return redact_flags("\n" + found + "\n")

    return Tool(
        name="search_role_skill",
        description=(
            "Search the skills bound to YOUR role in the shared flat skill library "
            "(methods, checklists, imported reference material) and return matching text. "
            "A card may name a related technique (e.g. 'SSTI', '信息搜集') — search that name "
            "to pull up its own card; there are no clickable links to follow."
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
        flag_source=False,  # library text is never evidence from the current target
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
