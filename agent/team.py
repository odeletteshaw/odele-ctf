"""Role-based team orchestration.

The console's "team" is a set of roles, not a token allocation:

- 团队长 (lead): reads the challenge and writes a short plan — no tools, no solving.
- 信息收集员 (recon): runs the category's tools to map the target and collect facts.
- 攻防专家 (expert): the direction specialist; solves with the plan + recon findings.
- 报告收集员 (reporter): writes the Chinese writeup plus a team review.

Stateful targets (pwn processes, AI chatbots) mutate as they are probed, so recon is
skipped for those directions; the lead -> expert -> reporter chain still runs.
"""

from dataclasses import dataclass, field
from typing import Any

from agent.loop import (
    EventFn,
    GuidanceFn,
    SolveResult,
    Tool,
    chat_fn,
    complete,
    extract_flags,
    run_loop,
)

LEAD = "lead"
RECON = "recon"
EXPERT = "expert"
REPORTER = "reporter"

# Probing these destroys state the expert needs, so recon is skipped.
SKIP_RECON = {"pwn", "ai"}

LEAD_SYSTEM = """你是 CTF 团队的团队长。你不直接解题，负责拆解题目、制定计划、分派侦察与解题。
只输出一份简洁计划（最多 10 行），包含：
1) 目标理解；2) 侦察重点（3-5 条，要具体到接口/文件/参数）；3) 专家执行要点（3-5 条）；4) 验证与收尾方式。
不要输出 flag，不要编造题目里没有的信息。"""

RECON_SYSTEM = """你是团队的信息收集员。用现有工具摸清目标，尽可能收集可利用的信息：
页面/表单/接口、参数与输入点、响应头与错误、技术栈与文件、泄露线索（备份/源码/配置）。
只做侦察，不要展开完整利用（顺手拿到 flag 除外）。
输出事实清单；每条都要附证据（URL、参数、响应片段或文件内容），不要臆测。"""

REPORTER_SYSTEM = """你是团队的报告收集员。根据题目、团队长计划、侦察结果、专家执行过程和最终结果，
写一份中文复盘，包含：
1) 题目与目标；2) 团队分工与执行（谁做了什么）；3) 关键发现与利用链；4) 成败原因；5) 最终 flag。
只写真实发生的内容，不要编造；约 300-500 字。"""


@dataclass
class TeamOutcome:
    result: SolveResult
    report: str
    timeline: list[dict[str, Any]] = field(default_factory=list)
    plan: str = ""
    recon: str = ""


def member(team: list[dict], role: str, category: str | None = None) -> dict:
    """Pick the configured member for a role (experts are matched by direction)."""
    for m in team or []:
        if m.get("role") != role:
            continue
        if role == EXPERT and category and category not in (m.get("directions") or []):
            continue
        return m
    if role == EXPERT:  # unknown direction: fall back to the first expert
        for m in team or []:
            if m.get("role") == EXPERT:
                return m
    return {"role": role, "name": role, "directions": [], "description": ""}


def _summary(text: str, limit: int = 400) -> str:
    return " ".join((text or "").split())[:limit]


def _expert_solve(
    tools: list[Tool],
    system: str,
    user: str,
    *,
    model: str | None,
    max_turns: int,
    on_event: EventFn | None,
    guidance: GuidanceFn | None,
    flag_pattern,
    persist: bool,
    diagnostic: str | None,
) -> SolveResult:
    chat = chat_fn(model)
    final_text, calls = run_loop(
        chat, tools, system, user, max_turns,
        on_event=on_event, guidance=guidance, flag_pattern=flag_pattern,
        persist=persist, diagnostic=diagnostic,
    )
    flags = extract_flags(final_text, flag_pattern)
    return SolveResult(flags[-1] if flags else None, final_text, calls)


def _transcript(events: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for ev in events[-70:]:
        kind = ev.get("type")
        if kind == "agent":
            lines.append(f"[agent] {ev.get('text', '')}")
        elif kind == "tool_call":
            lines.append(f"[tool {ev.get('name', '?')}] {ev.get('args', '')}")
        elif kind == "tool_result":
            out = str(ev.get("output", ""))
            lines.append("[result] " + (out[:600] + " …" if len(out) > 600 else out))
        elif kind == "guidance":
            lines.append(f"[supervisor] {ev.get('text', '')}")
    return "\n".join(lines)


def run_team(
    tools: list[Tool],
    system: str,
    user: str,
    *,
    team: list[dict],
    category: str,
    model: str | None = None,
    max_turns: int = 40,
    on_event: EventFn | None = None,
    guidance: GuidanceFn | None = None,
    flag_pattern=None,
    persist: bool = False,
    diagnostic: str | None = None,
) -> TeamOutcome:
    """Run the lead -> recon -> expert -> reporter chain and return the solve + review."""
    raw_emit = on_event or (lambda event: None)
    timeline: list[dict[str, Any]] = []

    def role_event(role: dict, status: str, summary: str = "") -> None:
        event = {"type": "role", "role": role.get("role"), "name": role.get("name"),
                 "status": status, "summary": summary}
        timeline.append(event)
        raw_emit(event)

    def scoped(role: dict) -> EventFn:
        def sink(event: dict[str, Any]) -> None:
            raw_emit({**event, "role": role.get("role"), "name": role.get("name")})
        return sink

    def say(role: dict, text: str) -> None:
        raw_emit({"type": "agent", "role": role.get("role"), "name": role.get("name"),
                  "text": text})

    tool_names = ", ".join(tool.name for tool in tools)
    direction = category

    # ---- lead: plan --------------------------------------------------------
    lead = member(team, LEAD, direction)
    role_event(lead, "start")
    plan = complete(
        LEAD_SYSTEM,
        f"方向：{direction}\n可用工具：{tool_names}\n\n题目：\n{user}\n\n请给出团队计划。",
        model=model,
    )
    if plan:
        say(lead, plan)
    role_event(lead, "end", _summary(plan))

    # ---- recon: collect facts ---------------------------------------------
    recon_text = ""
    recon = member(team, RECON, direction)
    recon_result: SolveResult | None = None
    if direction not in SKIP_RECON:
        role_event(recon, "start")
        recon_events: list[dict[str, Any]] = []

        def recon_sink(event: dict[str, Any]) -> None:
            recon_events.append(event)
            scoped(recon)(event)

        recon_user = (
            f"题目：\n{user}\n\n团队长计划：\n{plan or '(none)'}\n\n"
            "请完成侦察，输出事实清单（附证据）。"
        )
        recon_result = _expert_solve(
            tools, f"{RECON_SYSTEM}\n\n[类别要求]\n{system}", recon_user,
            model=model, max_turns=min(12, max_turns), on_event=recon_sink,
            guidance=None, flag_pattern=flag_pattern, persist=False,
            diagnostic=diagnostic,
        )
        recon_text = recon_result.final_text
        role_event(recon, "end", _summary(recon_text))
    else:
        role_event(recon, "skipped", "该类目标有状态，侦察会破坏专家所需的现场，跳过。")

    if recon_result is not None and recon_result.flag:
        result = recon_result
        expert_events: list[dict[str, Any]] = []
        expert = member(team, EXPERT, direction)
        role_event(expert, "skipped", "侦察阶段已拿到 flag。")
    else:
        # ---- expert: solve -------------------------------------------------
        expert = member(team, EXPERT, direction)
        role_event(expert, "start")
        expert_events: list[dict[str, Any]] = []

        def expert_sink(event: dict[str, Any]) -> None:
            expert_events.append(event)
            scoped(expert)(event)

        role_note = (
            f"[团队协作] 你是本队的{expert.get('name') or '攻防专家'}"
            f"（方向：{direction}）。团队长计划与侦察结果见下；先核对侦察事实，再独立完成利用并拿到 flag。"
        )
        expert_user = (
            f"题目：\n{user}\n\n团队长计划：\n{plan or '(none)'}\n\n"
            f"侦察结果：\n{recon_text or '(无)'}\n\n请解题。"
        )
        result = _expert_solve(
            tools, f"{system}\n\n{role_note}", expert_user,
            model=model, max_turns=max_turns, on_event=expert_sink,
            guidance=guidance, flag_pattern=flag_pattern, persist=persist,
            diagnostic=diagnostic,
        )
        role_event(expert, "end", _summary(result.final_text))

    # ---- reporter: writeup + team review ----------------------------------
    reporter = member(team, REPORTER, direction)
    role_event(reporter, "start")
    report = complete(
        REPORTER_SYSTEM,
        (
            f"题目：\n{user}\n\n团队长计划：\n{plan or '(none)'}\n\n"
            f"侦察结果：\n{recon_text or '(无)'}\n\n"
            f"专家执行过程：\n{_transcript(expert_events)}\n\n"
            f"最终 flag：{result.flag or '（未拿到）'}\n\n请写复盘。"
        ),
        model=model,
    )
    if report:
        say(reporter, report)
        raw_emit({"type": "writeup", "text": report})
    role_event(reporter, "end", _summary(report))

    return TeamOutcome(result=result, report=report, timeline=timeline, plan=plan,
                       recon=recon_text)
