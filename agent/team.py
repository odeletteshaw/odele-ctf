"""Role-based team orchestration.

The console's "team" is a set of roles, not a token allocation:

- 团队长 (lead): reads the challenge and writes a short plan — no tools, no solving.
- 信息收集员 (recon): runs the category's tools to map the target and collect facts.
- 攻防专家 (expert): the direction specialist; solves with the plan + recon findings.
- 报告收集员 (reporter): writes the Chinese writeup plus a team review.
- Custom roles (role=custom): the lead may ask for up to three by emitting
  {"invoke":[{"id","brief"}]} in its plan; they run before the expert.

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
from agent.skills import briefing, index, member_dirs, role_skill_tool

LEAD = "lead"
RECON = "recon"
EXPERT = "expert"
REPORTER = "reporter"

# Probing these destroys state the expert needs, so recon is skipped.
SKIP_RECON = {"pwn", "ai"}

# Recon is read-only-ish: no payload generators, no process/chat drivers, no code exec
# beyond the sandbox. Exact tool names; unknown names are dropped safely.
RECON_TOOLS = {
    "http_request", "http_batch", "download_file", "run_python", "search_knowledge",
    "triage", "strings", "disassemble",
}


def tools_for(role: str, tools: list[Tool], skill_tool: Tool | None) -> list[Tool]:
    """Role tool whitelist: lead/reporter none, recon read-only subset, expert all."""
    if role in (LEAD, REPORTER):
        return []
    if role == RECON:
        picked = [tool for tool in tools if tool.name in RECON_TOOLS]
    else:
        picked = list(tools)
    if skill_tool is not None:
        picked.append(skill_tool)
    return picked

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


def _json_objects(text: str) -> list[str]:
    """Top-level {...} objects in a text, string- and nesting-aware."""
    objects: list[str] = []
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start:index + 1])
                start = None
    return objects


def _parse_invocations(plan: str, limit: int = 3) -> list[dict[str, str]]:
    """Read the lead's {"invoke":[{"id","brief"}]} block (last valid object wins)."""
    import json
    for raw in reversed(_json_objects(plan)):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        invoke = data.get("invoke") if isinstance(data, dict) else None
        if not isinstance(invoke, list):
            continue
        picked = []
        for item in invoke:
            if isinstance(item, dict) and item.get("id"):
                picked.append({"id": str(item["id"]),
                               "brief": str(item.get("brief") or "")})
            if len(picked) >= limit:
                break
        return picked
    return []


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

    direction = category
    lead = member(team, LEAD, direction)
    recon = member(team, RECON, direction)
    expert = member(team, EXPERT, direction)
    reporter = member(team, REPORTER, direction)
    custom_roles = [m for m in team if m.get("role") == "custom"]

    lead_dirs = member_dirs(lead)
    recon_dirs = member_dirs(recon)
    expert_dirs = member_dirs(expert)
    reporter_dirs = member_dirs(reporter)
    lead_brief = briefing(lead_dirs)
    reporter_brief = briefing(reporter_dirs)
    recon_index = index(recon_dirs)
    expert_index = index(expert_dirs)

    # ---- lead: plan (+ optionally invoke custom roles) ---------------------
    role_event(lead, "start")
    roster: list[str] = []
    for role in custom_roles:
        skills = ", ".join(role.get("skills") or []) or "无"
        roster.append(f"- id: {role.get('id')} | {role.get('name')} | "
                      f"{role.get('description') or ''} | 技能包: {skills}")
    lead_user = (
        f"方向：{direction}\n"
        f"可用工具（侦察/专家/自定义角色）：{', '.join(tool.name for tool in tools)}\n\n"
        f"题目：\n{user}\n\n请给出团队计划。"
    )
    if custom_roles:
        lead_user += (
            "\n\n可调用的自定义角色（按需选择，最多 3 个；不需要就不要调用）：\n"
            + "\n".join(roster)
            + '\n\n在计划末尾单独输出一行 JSON，例如 '
              '{"invoke": [{"id": "角色id", "brief": "给它的具体任务"}]}；'
              '不需要调用时输出 {"invoke": []}。'
        )
    plan = complete(
        LEAD_SYSTEM + (f"\n\n[你的技能包]\n{lead_brief}" if lead_brief else ""),
        lead_user,
        model=model,
    )
    if plan:
        say(lead, plan)
    role_event(lead, "end", _summary(plan))
    invocations = _parse_invocations(plan) if custom_roles else []

    # ---- recon: collect facts ---------------------------------------------
    recon_text = ""
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
        recon_system = RECON_SYSTEM
        if recon_index:
            recon_system += (
                "\n\n[角色技能索引] 需要细节时调用 search_role_skill(query)：\n" + recon_index
            )
        recon_result = _expert_solve(
            tools_for(RECON, tools, role_skill_tool(recon_dirs)),
            f"{recon_system}\n\n[类别要求]\n{system}", recon_user,
            model=model, max_turns=min(12, max_turns), on_event=recon_sink,
            guidance=None, flag_pattern=flag_pattern, persist=False,
            diagnostic=diagnostic,
        )
        recon_text = recon_result.final_text
        role_event(recon, "end", _summary(recon_text))
    else:
        role_event(recon, "skipped", "该类目标有状态，侦察会破坏专家所需的现场，跳过。")

    result: SolveResult | None = None
    expert_events: list[dict[str, Any]] = []
    all_findings: list[str] = []

    if recon_result is not None and recon_result.flag:
        result = recon_result
        role_event(expert, "skipped", "侦察阶段已拿到 flag。")
    else:
        # ---- custom roles the lead asked for (on demand, in order) ---------
        by_id = {role.get("id"): role for role in custom_roles}
        for invocation in invocations:
            special = by_id.get(invocation.get("id"))
            if special is None:
                continue
            role_event(special, "start")
            dirs = member_dirs(special)
            skill_index = index(dirs)
            role_sink = scoped(special)
            role_events: list[dict[str, Any]] = []

            def custom_sink(event: dict[str, Any], _bucket=role_events, _sink=role_sink) -> None:
                _bucket.append(event)
                _sink(event)

            custom_system = (
                f"{system}\n\n[团队协作] 你是 {special.get('name')}。职责："
                f"{special.get('description') or '按团队长分派执行'}\n"
                "先核对侦察事实与已有发现，再执行任务；每个结论附证据。"
            )
            if skill_index:
                custom_system += (
                    "\n\n[角色技能索引] 需要细节时调用 search_role_skill(query)：\n"
                    + skill_index
                )
            custom_user = (
                f"题目：\n{user}\n\n团队长计划：\n{plan or '(none)'}\n\n"
                f"侦察结果：\n{recon_text or '(无)'}\n\n"
                f"已有发现：\n" + ("\n".join(all_findings) or "(无)") + "\n\n"
                f"你的任务：{invocation.get('brief') or '按职责支援解题'}\n"
                "能直接拿到 flag 就给；否则输出结论与证据。"
            )
            special_result = _expert_solve(
                tools_for(special.get("role", "custom"), tools, role_skill_tool(dirs)),
                custom_system, custom_user,
                model=model, max_turns=min(12, max_turns), on_event=custom_sink,
                guidance=None, flag_pattern=flag_pattern, persist=False,
                diagnostic=diagnostic,
            )
            all_findings.append(
                f"[{special.get('name')}] {special_result.final_text}"
            )
            role_event(special, "end", _summary(special_result.final_text))
            if special_result.flag:
                result = special_result
                break

        if result is not None:
            role_event(expert, "skipped", "自定义角色已拿到 flag。")
        else:
            # ---- expert: solve --------------------------------------------
            role_event(expert, "start")

            def expert_sink(event: dict[str, Any]) -> None:
                expert_events.append(event)
                scoped(expert)(event)

            role_note = (
                f"[团队协作] 你是本队的{expert.get('name') or '攻防专家'}"
                f"（方向：{direction}）。团队长计划、侦察结果与其他角色发现见下；"
                "先核对事实，再独立完成利用并拿到 flag。"
            )
            expert_user = (
                f"题目：\n{user}\n\n团队长计划：\n{plan or '(none)'}\n\n"
                f"侦察结果：\n{recon_text or '(无)'}\n\n"
                f"其他角色发现：\n" + ("\n".join(all_findings) or "(无)") + "\n\n请解题。"
            )
            expert_system = f"{system}\n\n{role_note}"
            if expert_index:
                expert_system += (
                    "\n\n[角色技能索引] 需要细节时调用 search_role_skill(query)：\n"
                    + expert_index
                )
            result = _expert_solve(
                tools_for(expert.get("role", EXPERT), tools, role_skill_tool(expert_dirs)),
                expert_system, expert_user,
                model=model, max_turns=max_turns, on_event=expert_sink,
                guidance=guidance, flag_pattern=flag_pattern, persist=persist,
                diagnostic=diagnostic,
            )
            role_event(expert, "end", _summary(result.final_text))

    # ---- reporter: writeup + team review ----------------------------------
    role_event(reporter, "start")
    report = complete(
        REPORTER_SYSTEM + (f"\n\n[你的技能包]\n{reporter_brief}" if reporter_brief else ""),
        (
            f"题目：\n{user}\n\n团队长计划：\n{plan or '(none)'}\n\n"
            f"侦察结果：\n{recon_text or '(无)'}\n\n"
            f"自定义角色发现：\n" + ("\n".join(all_findings) or "(无)") + "\n\n"
            f"专家执行过程：\n{_transcript(expert_events)}\n\n"
            f"最终 flag：{(result.flag if result else None) or '（未拿到）'}\n\n请写复盘。"
        ),
        model=model,
    )
    if report:
        say(reporter, report)
        raw_emit({"type": "writeup", "text": report})
    role_event(reporter, "end", _summary(report))

    return TeamOutcome(result=result, report=report, timeline=timeline, plan=plan,
                       recon=recon_text)
