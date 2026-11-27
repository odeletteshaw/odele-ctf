"""Team configuration: one lead plus a flat pool of worker roles.

The lead is the only role that receives the user's command; it assigns DAG nodes to
workers (no fixed pipeline). Roles bind skills from the flat library by id or tag
(`tag:web`); there are no per-role skill directories.

Stored in the settings table and edited on the Team page. Legacy configs
(lead/recon/expert/reporter + pack ids) are migrated on load.
"""

import json
import re
from pathlib import Path

from backend.settings import settings

LEGACY_PATH = Path.home() / ".odele-ctf" / "team.json"

LEAD_SKILLS = ["lead-method", "hello-ctf-skill", "hello-ctf-taxonomy"]
RECON_SKILLS = ["recon-method", "tag:recon", "hello-ctf-skill", "hello-ctf-taxonomy"]

DIRECTION_LABELS = {
    "web": "Web", "crypto": "Crypto", "misc": "Misc", "forensics": "Forensics",
    "pwn": "Pwn", "reverse": "Reverse", "ai": "AI", "cloud": "云安全",
    "blockchain": "区块链", "ics": "工控", "iot": "IoT", "ir": "应急响应",
    "pentest": "渗透测试",
}

DEFAULT_TEAM = [
    {"id": "lead", "role": "lead", "kind": "lead", "name": "团队长", "directions": [],
     "skills": LEAD_SKILLS,
     "description": "唯一接收用户命令的角色：拆解 DAG、分派扁平角色、汇总结果、提交审批"},
    {"id": "recon", "role": "worker", "kind": "recon", "name": "信息收集员", "directions": [],
     "skills": RECON_SKILLS,
     "description": "用工具摸清目标：接口、参数、技术栈、泄露线索，输出带证据的事实清单"},
    *[
        {"id": f"expert-{direction}", "role": "worker", "kind": "expert",
         "name": f"{DIRECTION_LABELS[direction]} 专家", "directions": [direction],
         "skills": ["common-method", f"tag:{direction}"],
         "description": f"{DIRECTION_LABELS[direction]} 方向攻防专家，按团队长分派解题"}
        for direction in DIRECTION_LABELS
    ],
    {"id": "reporter", "role": "worker", "kind": "reporter", "name": "报告收集员",
     "directions": [], "skills": ["reporter-method"],
     "description": "整理题解与团队复盘：分工、关键发现、利用链、成败原因"},
]

LEAD_ROLE = "lead"
WORKER_ROLE = "worker"
VALID_ROLES = {LEAD_ROLE, WORKER_ROLE}
VALID_KINDS = {"lead", "recon", "expert", "reporter", "custom", "worker"}

OLD_PACK_MAP = {
    "lead": "lead-method",
    "recon": "tag:recon",
    "reporter": "reporter-method",
    "experts/_common": "common-method",
}


def _slug(text: str) -> str:
    text = re.sub(r"[^\w一-鿿-]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-") or "role"


def _clean_selector(selector) -> str | None:
    selector = str(selector).strip()
    if not selector or selector.startswith("/") or ".." in selector:
        return None
    if not re.fullmatch(r"[\w一-鿿:./*-]+", selector):
        return None
    return selector


def _migrate_selector(selector: str) -> str | None:
    """Map old skill-pack ids to flat-library selectors."""
    if selector in OLD_PACK_MAP:
        return OLD_PACK_MAP[selector]
    if selector.startswith("experts/"):
        direction = selector.split("/", 1)[1]
        return "common-method" if direction == "_common" else f"tag:{direction}"
    if selector.startswith("roles/"):
        return None
    return selector


def _default_skills(role: str, kind: str, directions: list[str]) -> list[str]:
    if role == LEAD_ROLE:
        return list(LEAD_SKILLS)
    if kind == "recon":
        return list(RECON_SKILLS)
    if kind == "expert":
        packs = ["common-method"]
        packs += [f"tag:{d}" for d in directions]
        return packs
    if kind == "reporter":
        return ["reporter-method"]
    return []


def _legacy_file_team() -> list[dict] | None:
    if not LEGACY_PATH.exists():
        return None
    try:
        members = json.loads(LEGACY_PATH.read_text()).get("members")
    except (OSError, ValueError):
        return None
    return members if isinstance(members, list) and members else None


def _normalize(members: list) -> list[dict]:
    """Give every member a stable id, map legacy roles, and normalize skill selectors."""
    cleaned: list[dict] = []
    used: set[str] = set()
    for m in members or []:
        if not isinstance(m, dict):
            continue
        old_role = str(m.get("role") or "")
        if old_role in {"lead", LEAD_ROLE}:
            role, kind = LEAD_ROLE, "lead"
        else:
            role = WORKER_ROLE
            kind = str(m.get("kind") or old_role or "worker")
            if kind not in VALID_KINDS:
                kind = "worker"
        name = str(m.get("name") or kind).strip()[:80] or kind
        base = str(m.get("id") or _slug(name))[:60]
        member_id = base
        suffix = 2
        while member_id in used:
            member_id = f"{base}-{suffix}"
            suffix += 1
        used.add(member_id)
        directions = [str(d) for d in (m.get("directions") or [])]
        if "skills" in m:
            raw_skills = m.get("skills") or []
        else:
            raw_skills = _default_skills(role, kind, directions)
        skills: list[str] = []
        for raw in raw_skills:
            mapped = _migrate_selector(_clean_selector(raw) or "")
            if mapped and mapped not in skills:
                skills.append(mapped)
        cleaned.append({
            "id": member_id,
            "role": role,
            "kind": kind,
            "name": name,
            "directions": directions,
            "description": str(m.get("description") or "")[:500],
            "skills": skills,
            "mcp": m.get("mcp") if isinstance(m.get("mcp"), list) else [],
        })
    return cleaned


def load_team() -> list[dict]:
    stored = settings.get("team")
    if isinstance(stored, list) and stored:
        if all(isinstance(m, dict) and m.get("role") for m in stored):
            return _normalize(stored)
        settings.set("team", DEFAULT_TEAM)
        return _normalize(DEFAULT_TEAM)
    if _legacy_file_team():
        settings.set("team", DEFAULT_TEAM)
        return _normalize(DEFAULT_TEAM)
    return _normalize(DEFAULT_TEAM)


def save_team(members: list[dict]) -> int:
    cleaned = _normalize(members)
    # keep exactly one lead at most: promote the first lead, demote the rest
    leads = [m for m in cleaned if m["role"] == LEAD_ROLE]
    if len(leads) > 1:
        for extra in leads[1:]:
            extra["role"] = WORKER_ROLE
            extra["kind"] = "worker"
    if cleaned:
        settings.set("team", cleaned)
    return len(cleaned)


def create_role(name: str, description: str = "", skills: list[str] | None = None) -> dict:
    """Add a flat worker role (invoked on demand by the lead)."""
    name = name.strip()
    if not name:
        raise ValueError("name is required")
    team = load_team()
    used = {m["id"] for m in team}
    base = _slug(name)
    member_id = base
    suffix = 2
    while member_id in used:
        member_id = f"{base}-{suffix}"
        suffix += 1
    selectors = []
    for raw in skills or []:
        mapped = _clean_selector(raw)
        if mapped and mapped not in selectors:
            selectors.append(mapped)
    member = {
        "id": member_id,
        "role": WORKER_ROLE,
        "kind": "custom",
        "name": name[:80],
        "directions": [],
        "description": description[:500],
        "skills": selectors,
        "mcp": [],
    }
    team.append(member)
    save_team(team)
    return member


def delete_role(member_id: str) -> bool:
    team = load_team()
    kept = [m for m in team if m.get("id") != member_id or m["role"] == LEAD_ROLE]
    if len(kept) == len(team):
        return False
    save_team(kept)
    return True
