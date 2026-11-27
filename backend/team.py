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
from pathlib import Path

from backend.settings import settings

LEGACY_PATH = Path.home() / ".odele-ctf" / "team.json"

DEFAULT_TEAM = [
    {"role": "lead", "name": "团队长", "directions": [],
     "description": "拆解题目、制定计划、分派侦察与专家、汇总结论"},
    {"role": "recon", "name": "信息收集员", "directions": [],
     "description": "用工具摸清目标：接口、参数、技术栈、泄露线索，输出带证据的事实清单"},
    {"role": "expert", "name": "Web 专家", "directions": ["web"],
     "description": "Web 渗透：注入、鉴权绕过、SSRF、XXE、反序列化、模板注入等"},
    {"role": "expert", "name": "Crypto 专家", "directions": ["crypto"],
     "description": "密码学：RSA、对称、ECC、PRNG、格与 oracle 攻击"},
    {"role": "expert", "name": "Misc 专家", "directions": ["misc"],
     "description": "杂项：编码、esolang、编程题、受限环境逃逸"},
    {"role": "expert", "name": "Forensics 专家", "directions": ["forensics"],
     "description": "取证：文件雕刻、归档、pcap、隐写、协议还原"},
    {"role": "expert", "name": "Pwn 专家", "directions": ["pwn"],
     "description": "二进制利用：溢出、格式化串、canary、shellcode、heap"},
    {"role": "expert", "name": "Reverse 专家", "directions": ["reverse"],
     "description": "逆向：反汇编、符号执行、字节码与自定义 VM"},
    {"role": "expert", "name": "AI 专家", "directions": ["ai"],
     "description": "提示注入红队：越狱、prompt leaking、绕过输入/输出过滤"},
    {"role": "reporter", "name": "报告收集员", "directions": [],
     "description": "整理题解与团队复盘：分工、关键发现、利用链、成败原因"},
]

VALID_ROLES = {"lead", "recon", "expert", "reporter"}


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


def load_team() -> list[dict]:
    stored = settings.get("team")
    if isinstance(stored, list) and stored:
        if _is_role_team(stored):
            return stored
        _seed_slots_from_legacy(stored)
        settings.set("team", DEFAULT_TEAM)
        return DEFAULT_TEAM
    legacy = _legacy_file_team()
    if legacy:
        _seed_slots_from_legacy(legacy)
        settings.set("team", DEFAULT_TEAM)
        return DEFAULT_TEAM
    return DEFAULT_TEAM


def save_team(members: list[dict]) -> int:
    cleaned = []
    for m in members:
        if not isinstance(m, dict) or m.get("role") not in VALID_ROLES:
            continue
        member = {
            "role": m["role"],
            "name": str(m.get("name") or m["role"])[:80],
            "directions": [str(d) for d in (m.get("directions") or [])],
            "description": str(m.get("description") or "")[:500],
        }
        cleaned.append(member)
    if cleaned:
        settings.set("team", cleaned)
    return len(cleaned)
