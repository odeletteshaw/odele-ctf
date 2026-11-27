"""Role team configuration: lead, recon, one expert per direction, reporter.

This is the team that actually works a challenge (agent/team.py runs it). It is NOT
the platform token allocation — that is a separate concept, see backend/slots.py.

Members are stored in the settings table and edited on the Team page. Each member:
    {"role": "lead"|"recon"|"expert"|"reporter", "name": str,
     "directions": [..]   # experts only
     "description": str}

Legacy team data was a direction -> token_index mapping; it is migrated once into
token_slots and replaced by DEFAULT_TEAM.
"""

import json
import re
from pathlib import Path

from backend.settings import settings

LEGACY_PATH = Path.home() / ".odele-ctf" / "team.json"

DEFAULT_TEAM = [
    {"id": "lead", "role": "lead", "name": "团队长", "directions": [],
     "skills": ["lead"],
     "description": "拆解题目、制定计划、分派侦察与专家、汇总结论"},
    {"id": "recon", "role": "recon", "name": "信息收集员", "directions": [],
     "skills": ["recon"],
     "description": "用工具摸清目标：接口、参数、技术栈、泄露线索，输出带证据的事实清单"},
    {"id": "expert-web", "role": "expert", "name": "Web 专家", "directions": ["web"],
     "skills": ["experts/_common", "experts/web"],
     "description": "Web 渗透：注入、鉴权绕过、SSRF、XXE、反序列化、模板注入等"},
    {"id": "expert-crypto", "role": "expert", "name": "Crypto 专家", "directions": ["crypto"],
     "skills": ["experts/_common", "experts/crypto"],
     "description": "密码学：RSA、对称、ECC、PRNG、格与 oracle 攻击"},
    {"id": "expert-misc", "role": "expert", "name": "Misc 专家", "directions": ["misc"],
     "skills": ["experts/_common", "experts/misc"],
     "description": "杂项：编码、esolang、编程题、受限环境逃逸"},
    {"id": "expert-forensics", "role": "expert", "name": "Forensics 专家", "directions": ["forensics"],
     "skills": ["experts/_common", "experts/forensics"],
     "description": "取证：文件雕刻、归档、pcap、隐写、协议还原"},
    {"id": "expert-pwn", "role": "expert", "name": "Pwn 专家", "directions": ["pwn"],
     "skills": ["experts/_common", "experts/pwn"],
     "description": "二进制利用：溢出、格式化串、canary、shellcode、heap"},
    {"id": "expert-reverse", "role": "expert", "name": "Reverse 专家", "directions": ["reverse"],
     "skills": ["experts/_common", "experts/reverse"],
     "description": "逆向：反汇编、符号执行、字节码与自定义 VM"},
    {"id": "expert-ai", "role": "expert", "name": "AI 专家", "directions": ["ai"],
     "skills": ["experts/_common", "experts/ai"],
     "description": "提示注入红队：越狱、prompt leaking、绕过输入/输出过滤"},
    {"id": "expert-cloud", "role": "expert", "name": "云安全专家", "directions": ["cloud"],
     "skills": ["experts/_common", "experts/cloud"],
     "description": "云环境攻防：IAM 提权、容器逃逸、云存储/元数据、DevOps 泄露"},
    {"id": "expert-blockchain", "role": "expert", "name": "区块链专家", "directions": ["blockchain"],
     "skills": ["experts/_common", "experts/blockchain"],
     "description": "智能合约审计与链上攻击：重入、溢出、权限、代理与交易分析"},
    {"id": "expert-ics", "role": "expert", "name": "工控专家", "directions": ["ics"],
     "skills": ["experts/_common", "experts/ics"],
     "description": "工控安全：PLC/SCADA 协议、固件、控制逻辑与通信劫持"},
    {"id": "expert-iot", "role": "expert", "name": "IoT 专家", "directions": ["iot"],
     "skills": ["experts/_common", "experts/iot"],
     "description": "物联网安全：固件提取/逆向、无线协议、硬件接口与设备漏洞"},
    {"id": "expert-ir", "role": "expert", "name": "应急响应专家", "directions": ["ir"],
     "skills": ["experts/_common", "experts/ir"],
     "description": "事件响应：日志与流量分析、入侵排查、失陷溯源"},
    {"id": "expert-pentest", "role": "expert", "name": "渗透测试专家", "directions": ["pentest"],
     "skills": ["experts/_common", "experts/pentest"],
     "description": "内网/外网渗透：信息搜集、提权、横向移动、隧道与后渗透"},
    {"id": "reporter", "role": "reporter", "name": "报告收集员", "directions": [],
     "skills": ["reporter"],
     "description": "整理题解与团队复盘：分工、关键发现、利用链、成败原因"},
]

VALID_ROLES = {"lead", "recon", "expert", "reporter", "custom"}


def _seed_slots_from_legacy(members: list[dict]) -> None:
    """Carry a legacy direction->token_index mapping into token_slots."""
    if settings.get("token_slots") is not None:
        return
    mapping: dict[str, int] = {}
    for m in members:
        for direction in m.get("directions") or []:
            try:
                mapping[str(direction)] = int(m.get("token_index", 0))
            except (TypeError, ValueError):
                mapping[str(direction)] = 0
    if mapping:
        settings.set("token_slots", mapping)


def _legacy_file_team() -> list[dict] | None:
    if not LEGACY_PATH.exists():
        return None
    try:
        members = json.loads(LEGACY_PATH.read_text()).get("members")
    except (OSError, ValueError):
        return None
    return members if isinstance(members, list) and members else None


def _is_role_team(members: list) -> bool:
    return bool(members) and all(
        isinstance(m, dict) and m.get("role") in VALID_ROLES for m in members
    )


def _slug(text: str) -> str:
    text = re.sub(r"[^\w一-鿿-]+", "-", text.strip().lower())
    return re.sub(r"-+", "-", text).strip("-") or "role"


def _clean_pack(pack) -> str | None:
    pack = str(pack).strip()
    if not pack or pack.startswith("/") or ".." in pack.split("/"):
        return None
    if not re.fullmatch(r"[\w一-鿿./-]+", pack):
        return None
    return pack


def _normalize(members: list) -> list[dict]:
    """Give every member a stable id plus normalized fields (used by API and runtime)."""
    cleaned: list[dict] = []
    used: set[str] = set()
    for m in members or []:
        if not isinstance(m, dict) or m.get("role") not in VALID_ROLES:
            continue
        role = m["role"]
        name = str(m.get("name") or role).strip()[:80] or role
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
        elif role == "expert":
            raw_skills = ["experts/_common"] + [f"experts/{d}" for d in directions]
        elif role in {"lead", "recon", "reporter"}:
            raw_skills = [role]
        else:
            raw_skills = []
        skills = []
        for pack in raw_skills:
            pack = _clean_pack(pack)
            if pack and pack not in skills:
                skills.append(pack)
        cleaned.append({
            "id": member_id,
            "role": role,
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
        if _is_role_team(stored):
            return _normalize(stored)
        _seed_slots_from_legacy(stored)
        settings.set("team", DEFAULT_TEAM)
        return _normalize(DEFAULT_TEAM)
    legacy = _legacy_file_team()
    if legacy:
        _seed_slots_from_legacy(legacy)
        settings.set("team", DEFAULT_TEAM)
        return _normalize(DEFAULT_TEAM)
    return _normalize(DEFAULT_TEAM)


def save_team(members: list[dict]) -> int:
    cleaned = _normalize(members)
    if cleaned:
        settings.set("team", cleaned)
    return len(cleaned)


def create_role(name: str, description: str = "", skills: list[str] | None = None) -> dict:
    """Add a custom role (on-demand specialist) and its own skill pack directory."""
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
    packs = []
    for pack in skills or []:
        clean = _clean_pack(pack)
        if clean and clean not in packs:
            packs.append(clean)
    if not packs:
        packs = [f"roles/{member_id}"]
    member = {
        "id": member_id,
        "role": "custom",
        "name": name[:80],
        "directions": [],
        "description": description[:500],
        "skills": packs,
        "mcp": [],
    }
    team.append(member)
    save_team(team)

    if f"roles/{member_id}" in packs:
        from agent.skills import ROOT
        folder = ROOT / "roles" / member_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "references").mkdir(exist_ok=True)
        skill_md = folder / "SKILL.md"
        if not skill_md.exists():
            skill_md.write_text(
                f"# {name}\n\n**一句话**：{description or '自定义角色技能包，按需补充方法。'}\n\n"
                "## 工作方式\n\n- 先核对团队长/侦察给的事实，再执行本角色职责。\n"
                "- 需要细节时使用 search_role_skill 检索本包。\n",
                encoding="utf-8",
            )
    return member


def delete_role(member_id: str) -> bool:
    """Remove a member from the team config (its skill directory is kept)."""
    team = load_team()
    kept = [m for m in team if m.get("id") != member_id]
    if len(kept) == len(team):
        return False
    save_team(kept)
    return True
