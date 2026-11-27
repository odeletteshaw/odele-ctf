"""Import role skill material into agent/team_skills/<role>/references/.

Usage:
    python scripts/import_skills.py --list
    python scripts/import_skills.py --role expert-web --source ~/ctf-materials/web
    python scripts/import_skills.py --role recon --source ./notes.md --dry-run

Supported inputs: .md/.txt/.py/.js/.ts/.sh/.c/.cpp/.java/.json/.yaml/.yml/.html/
.xml/.csv (copied as Markdown, code fenced) and .pdf (text extracted when pypdf is
installed). Files are placed under the role's references/ directory and are picked
up automatically by agent/skills.py; restart the backend only if you want the
Team page counts to refresh immediately.
"""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "agent" / "team_skills"
DIRECTIONS = {"web", "crypto", "misc", "forensics", "pwn", "reverse", "ai",
              "cloud", "blockchain", "ics", "iot", "ir", "pentest"}
TEXT_EXT = {".md", ".txt", ".py", ".js", ".ts", ".sh", ".c", ".cpp", ".java", ".json",
            ".yaml", ".yml", ".html", ".xml", ".csv"}
MAX_BYTES = 400_000


def role_dir(role: str, root: Path = ROOT) -> Path:
    if role in {"lead", "recon", "reporter", "shared"}:
        return root / role if role != "shared" else root / "_shared"
    if role == "expert":
        return root / "experts" / "_common"
    if role.startswith("expert-"):
        direction = role[len("expert-"):]
        if direction not in DIRECTIONS:
            raise SystemExit(f"unknown direction {direction!r}; use one of {sorted(DIRECTIONS)}")
        return root / "experts" / direction
    raise SystemExit("--role must be shared, lead, recon, reporter, expert, or expert-<direction>")


def slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w一-鿿.-]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-.") or "material"


def wrap_text(title: str, source: str, content: str, suffix: str) -> str:
    if suffix == ".md":
        # Keep frontmatter and existing headings as-is; only add a title when the
        # document has no markdown heading at all.
        head = "\n".join(content.splitlines()[:40])
        body = content if ("# " in head or content.lstrip().startswith("---")) \
            else f"# {title}\n\n{content}"
        return body.rstrip() + "\n"
    lang = {".py": "python", ".js": "javascript", ".ts": "typescript", ".sh": "bash",
            ".c": "c", ".cpp": "cpp", ".java": "java", ".json": "json",
            ".yaml": "yaml", ".yml": "yaml", ".html": "html", ".xml": "xml",
            ".csv": "csv"}.get(suffix, "")
    return (
        f"# {title}\n\n来源：`{source}`\n\n```{lang}\n{content.rstrip()}\n```\n"
    )


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
    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        if path.suffix.lower() in TEXT_EXT or path.suffix.lower() == ".pdf":
            files.append(path)
    return files


def ensure_skill_md(target: Path, role: str, imported: list[str], dry: bool) -> None:
    skill = target / "SKILL.md"
    stamp = dt.date.today().isoformat()
    lines = "\n".join(f"- {name}" for name in imported)
    section = f"\n## 导入记录（{stamp}）\n{lines}\n"
    if dry:
        print(f"  · would {'append to' if skill.exists() else 'create'} {skill.relative_to(ROOT.parent.parent)}")
        return
    target.mkdir(parents=True, exist_ok=True)
    if skill.exists():
        with skill.open("a", encoding="utf-8") as fh:
            fh.write(section)
    else:
        skill.write_text(
            f"# {role} 技能包\n\n**一句话**：角色专属方法与资料，按需检索使用。\n"
            f"{section}",
            encoding="utf-8",
        )


def cmd_list(role: str | None, root: Path) -> None:
    sys.path.insert(0, str(ROOT.parent.parent))
    from agent.skills import entries, skill_dirs
    roles = [role] if role else ["lead", "recon", "reporter", "expert"] + [
        f"expert-{d}" for d in sorted(DIRECTIONS)
    ]
    for name in roles:
        lookup_role, _, direction = name.partition("-") if name.startswith("expert-") else (name, "", None)
        dirs = skill_dirs(lookup_role, direction)
        if name == "expert":
            dirs = skill_dirs("expert", None)
        items = entries(dirs)
        print(f"{name:14s} {'/'.join(str(d.relative_to(ROOT)) for d in dirs) or '(none)':28s} {len(items)} 篇")
        for entry in items:
            print(f"    - {entry['name']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", help="lead | recon | reporter | expert | expert-<direction>")
    parser.add_argument("--source", action="append", default=[], help="file or directory (repeatable)")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list", action="store_true", help="show current skill packs")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    if args.list:
        cmd_list(args.role, root)
        return
    if not args.role or not args.source:
        parser.error("--role and at least one --source are required (or use --list)")

    target = role_dir(args.role, root)
    refs = target / "references"
    print(f"role: {args.role} -> {target}")
    imported: list[str] = []
    seen: set[str] = set()
    for source_arg in args.source:
        source = Path(source_arg).expanduser()
        if not source.exists():
            print(f"  ! missing source: {source}")
            continue
        files = collect(source)
        print(f"source: {source} ({len(files)} candidate files)")
        for path in files:
            size = path.stat().st_size
            if size > MAX_BYTES:
                print(f"  ! skip large file ({size} bytes): {path}")
                continue
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                content = read_pdf(path)
                if not content:
                    continue
                title = path.stem
                body = f"# {title}\n\n{content}\n"
            else:
                try:
                    content = path.read_text(errors="replace")
                except OSError as error:
                    print(f"  ! skip {path}: {error}")
                    continue
                rel = str(path.relative_to(source)) if source.is_dir() else path.name
                title = Path(rel).stem
                body = wrap_text(title, rel, content, suffix)
            name = slug(path.stem if source.is_file() else str(path.relative_to(source).with_suffix("")))
            candidate = name
            i = 2
            while candidate in seen:
                candidate = f"{name}-{i}"
                i += 1
            seen.add(candidate)
            dest = refs / f"{candidate}.md"
            print(f"  + {path} -> {dest.relative_to(root) if dest.is_relative_to(root) else dest}")
            if not args.dry_run:
                refs.mkdir(parents=True, exist_ok=True)
                dest.write_text(body, encoding="utf-8")
            imported.append(candidate)

    if imported:
        ensure_skill_md(target, args.role, imported, args.dry_run)
    print(f"imported {len(imported)} file(s){' (dry run)' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
