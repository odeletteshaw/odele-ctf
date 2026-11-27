"""Knowledge harvesting with anti-bloat rules.

The harvester role may write at most MAX_PER_RUN new cards per solve. A card is
rejected when it duplicates an existing skill, carries challenge-specific data
(flags, localhost/dasctf hosts), lacks an existing tag, or is too short/long.
Card content stays generic: trigger, steps, evidence, pitfalls.
"""

import datetime as dt
import re
from typing import Any

import agent.skills as skills
from agent.loop import Tool

MAX_BODY = 6000
MIN_BODY = 120
MAX_PER_RUN = 2
FORBIDDEN = re.compile(
    r"flag\{|CTF2\{|https?://(?:127\.0\.0\.1|localhost|[\w.-]+\.dasctf\.com)", re.I
)


def _slug(text: str) -> str:
    text = re.sub(r"[^\w一-鿿-]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-") or "harvested-skill"


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\w]+", text.lower()) if len(t) >= 2]


def harvest_tool(max_cards: int = MAX_PER_RUN) -> Tool:
    written = 0

    def handler(args: dict[str, Any]) -> str:
        nonlocal written
        title = str(args.get("title") or "").strip()
        description = str(args.get("description") or "").strip()
        body = str(args.get("body") or "").strip()
        raw_tags = args.get("tags") or []
        if not title or not description or not body:
            return "Error: title, description and body are required."
        if len(title) > 80 or len(description) > 200:
            return "Rejected: title <= 80 chars, description <= 200 chars."
        if not (MIN_BODY <= len(body) <= MAX_BODY):
            return f"Rejected: body must be {MIN_BODY}-{MAX_BODY} chars (got {len(body)})."
        if FORBIDDEN.search(f"{description}\n{body}"):
            return ("Rejected: challenge-specific data (flag/CTF2 flag/localhost/dasctf host) "
                    "must not go into the shared library. Write the reusable technique only.")
        if written >= max_cards:
            return f"Rejected: per-solve limit reached ({max_cards} new cards)."

        library_tags = set(skills.tags())
        tags = []
        for raw in raw_tags if isinstance(raw_tags, list) else []:
            tag = str(raw).strip()
            if tag in library_tags and tag not in tags:
                tags.append(tag)
        if not tags:
            return ("Rejected: tags must come from the existing library tags "
                    f"({', '.join(sorted(library_tags))}). Pick the 1-3 that fit.")
        tags = tags[:6]
        if "harvested" not in tags:
            tags.append("harvested")

        skill_id = _slug(title)
        existing = {e["id"]: e for e in skills.entries()}
        if skill_id in existing:
            return f"Already covered by {skill_id}; skipped (do not duplicate)."
        title_tokens = set(_tokens(title))
        if title_tokens:
            for entry in existing.values():
                other = set(_tokens(entry["name"])) | set(_tokens(entry["description"]))
                overlap = len(title_tokens & other) / len(title_tokens)
                if overlap >= 0.8:
                    return f"Already covered by {entry['id']}; skipped (near-duplicate title)."

        if not body.lstrip().startswith("# "):
            body = f"# {title}\n\n{body}"
        text = (
            "---\n"
            f"id: {skill_id}\n"
            f"name: {title}\n"
            f"description: {description}\n"
            f"tags: [{', '.join(tags)}]\n"
            "source: harvested\n"
            f"imported_at: {dt.date.today().isoformat()}\n"
            "---\n\n"
            + body.strip() + "\n"
        )
        skills.LIBRARY.mkdir(parents=True, exist_ok=True)
        (skills.LIBRARY / f"{skill_id}.md").write_text(text, encoding="utf-8")
        skills._CACHE.update(stamp=None, entries=[])  # force a re-read on next access
        written += 1
        return (
            f"Saved new skill {skill_id} ({written}/{max_cards} this solve). "
            "Do not write another card unless it is a genuinely different technique."
        )

    return Tool(
        name="harvest_skill",
        description=(
            "Add ONE reusable, previously-uncovered technique to the shared skill library. "
            "Rules enforced: max 2 new cards per solve; no flags/target hosts; tags must be "
            "existing library tags; body 120-6000 chars; duplicates/near-duplicates refused. "
            "Skip harvesting when the technique is already covered."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Technique title (<=80 chars), no challenge name."},
                "description": {"type": "string", "description": "One-line summary (<=200 chars)."},
                "tags": {"type": "array", "items": {"type": "string"},
                         "description": "1-3 existing library tags, e.g. ['web','sql']."},
                "body": {"type": "string",
                         "description": "Markdown: trigger signals, steps, evidence, pitfalls (120-6000 chars)."},
            },
            "required": ["title", "description", "tags", "body"],
        },
        handler=handler,
    )
