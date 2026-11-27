"""Import skill material into the flat library (agent/skill_library/).

Usage:
    python scripts/import_skills.py --list [--search web]
    python scripts/import_skills.py --source ~/notes/web --tags web,hello-ctf --id-prefix web
    python scripts/import_skills.py --source ./paper.pdf --tags crypto --dry-run

Each file becomes agent/skill_library/<id>.md with frontmatter (id/name/
description/tags). Roles bind skills by id or `tag:<tag>`, so the library stays
flat — there are no per-role directories.
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "agent" / "skill_library"
TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".sh", ".c", ".cpp", ".java", ".json",
            ".yaml", ".yml", ".html", ".xml", ".csv"}
MAX_BYTES = 400_000


def slug(text: str) -> str:
    text = re.sub(r"[^\w一-鿿.-]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-.") or "skill"


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def title_of(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def desc_of(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("**一句话**"):
            return s[len("**一句话**"):].strip(" ：:")
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith(("#", ">", "|", "-", "```")):
            return s[:160]
    return ""


def wrap_md(title: str, source: str, content: str, suffix: str) -> str:
    if suffix == ".md":
        head = "\n".join(content.splitlines()[:40])
        body = content if ("# " in head or content.lstrip().startswith("---")) \
            else f"# {title}\n\n{content}"
        return body
    lang = {".py": "python", ".js": "javascript", ".ts": "typescript", ".sh": "bash",
            ".c": "c", ".cpp": "cpp", ".java": "java", ".json": "json",
            ".yaml": "yaml", ".yml": "yaml", ".html": "html", ".xml": "xml",
            ".csv": "csv"}.get(suffix, "")
    return f"# {title}\n\n来源：`{source}`\n\n```{lang}\n{content.rstrip()}\n```\n"


def read_pdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        print(f"  ! skip PDF (pypdf not installed): {path}")
        return None
    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as error:
        print(f"  ! skip PDF {path}: {error}")
        return None
    text = "\n\n".join(p for p in pages if p)
    return text or None


def collect(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    files = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        if path.suffix.lower() in TEXT_EXT or path.suffix.lower() == ".pdf":
            files.append(path)
    return files


def existing_ids() -> set[str]:
    return {p.stem for p in LIBRARY.glob("*.md")}


def write_skill(path: Path, source: Path, tags: list[str], id_prefix: str,
                dry: bool) -> str | None:
    suffix = path.suffix.lower()
    if path.stat().st_size > MAX_BYTES:
        print(f"  ! skip large file: {path}")
        return None
    if suffix == ".pdf":
        content = read_pdf(path)
        if not content:
            return None
        raw = f"# {path.stem}\n\n{content}\n"
    else:
        try:
            raw = path.read_text(errors="replace")
        except OSError as error:
            print(f"  ! skip {path}: {error}")
            return None
        raw = wrap_md(path.stem, str(path), raw, suffix)

    body = strip_frontmatter(raw)
    title = title_of(body, path.stem)
    desc = desc_of(body) or path.stem
    skill_id = slug(f"{id_prefix}-{path.stem}" if id_prefix else path.stem)
    base, i = skill_id, 2
    used = existing_ids()
    while base in used:
        base = f"{skill_id}-{i}"
        i += 1
    text = (
        "---\n"
        f"id: {base}\n"
        f"name: {title}\n"
        f"description: {desc}\n"
        f"tags: [{', '.join(tags)}]\n"
        f"source: {str(path)}\n"
        f"imported_at: {dt.date.today().isoformat()}\n"
        "---\n\n"
        + body.strip() + "\n"
    )
    dest = LIBRARY / f"{base}.md"
    print(f"  + {path} -> {dest.relative_to(ROOT)}")
    if not dry:
        LIBRARY.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return base


def cmd_list(search: str | None) -> None:
    sys.path.insert(0, str(ROOT))
    from agent.skills import entries
    items = entries()
    needle = (search or "").lower()
    for entry in items:
        haystack = f"{entry['id']} {entry['name']} {entry['description']} {' '.join(entry['tags'])}".lower()
        if needle and needle not in haystack:
            continue
        print(f"{entry['id']:38s} [{','.join(entry['tags'])}] {entry['name']}")
    print(f"total {len(items)} skill(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], help="file or directory (repeatable)")
    parser.add_argument("--tags", default="", help="comma-separated tags, e.g. web,hello-ctf")
    parser.add_argument("--id-prefix", default="", help="prefix for generated ids, e.g. web")
    parser.add_argument("--list", action="store_true", help="list the flat library")
    parser.add_argument("--search", default=None, help="filter --list output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list:
        cmd_list(args.search)
        return
    if not args.source:
        parser.error("--source is required (or use --list)")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    imported = 0
    for source_arg in args.source:
        source = Path(source_arg).expanduser()
        if not source.exists():
            print(f"  ! missing source: {source}")
            continue
        files = collect(source)
        print(f"source: {source} ({len(files)} candidate files), tags={tags or '-'}")
        for path in files:
            if write_skill(path, source, tags, args.id_prefix, args.dry_run):
                imported += 1
    print(f"imported {imported} skill(s){' (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
