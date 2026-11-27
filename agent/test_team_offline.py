"""Offline test of the role team (no API key): fake lead + fake chat.

Covers: a flag the user hands over via ask_user is a hint, never a result or a
submission candidate; the lead re-plans after recon (adding another direction);
the harvester runs after a solve; joined-fragment prose is not a flag.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from types import SimpleNamespace as NS
import agent.team as T
from agent.loop import Tool, flag_candidates

FLAG = "DASCTF{d91c2bd2d78dfc928169f1f35c88c1a2}"
assert flag_candidates("DASCTF{d91c2bd2d78dfc9` + `28169f1f35c88c1a2}") == [], "junk kept"
assert flag_candidates("DASCTF{d91c2bd2d78dfc9 + 28169f1f35c88c1a2}") == []
assert flag_candidates("flag{and 1=1}") == ["flag{and 1=1}"]

def msg(text=None, calls=None):
    tc = [NS(id=f"c{i}", function=NS(name=n, arguments=json.dumps(a))) for i, (n, a) in enumerate(calls or [])]
    return NS(content=text, tool_calls=tc or None)

def run(reverse_reproduces):
    plans = []
    def complete(system, user, model=None):
        plans.append(user)
        if len(plans) == 1:
            return '{"summary":"s","nodes":[{"id":"n1","role":"recon","task":"recon"},{"id":"n2","role":"expert-web","task":"web","depends_on":["n1"]},{"id":"h","role":"harvest","task":"x"}]}'
        if len(plans) == 2:  # after recon
            return '{"summary":"web+reverse","nodes":[{"id":"n1","role":"expert-web","task":"web","depends_on":["n1"]},{"id":"n3","role":"expert-reverse","task":"deobfuscate JS","depends_on":["n1"]}]}'
        return '{"summary":"none","nodes":[]}'
    state = {}
    def chat_fn(model=None):
        def chat(messages, tools):
            system = messages[0]["content"]; n = sum(1 for m in messages if m["role"] == "assistant")
            if "信息收集员" in system:
                return msg("前端 JS 混淆在 /src/views/Player.js")
            if "Web 专家" in system:
                if n == 0: return msg(calls=[("ask_user", {"question": "TLS blocked"})])
                return msg(f"The user's response resolved it: {FLAG}")
            if "Reverse 专家" in system:
                if n == 0: return msg(calls=[("fetch_and_decode", {})])
                return msg(f"decoded: {FLAG}")
            if "知识收割员" in system:
                state["harvest"] = True; return msg("已有覆盖，跳过")
            if "报告收集员" in system:
                return msg("# 题解：x\n## 1. 题目与目标\n...\n## 2. 侦察与发现\n...\n## 3. 利用步骤\n...\n## 4. 关键证据\n...\n## 5. 结论与 flag\n" + ("x" * 150))
            return msg("?")
        return chat
    T.complete = complete; T.chat_fn = chat_fn
    out = "flag hidden" if not reverse_reproduces else f"FLAG: {FLAG}"
    tools = [Tool("fetch_and_decode", "d", {"type": "object", "properties": {}}, lambda a: out)]
    team = [{"id": "lead", "role": "lead", "name": "团队长"},
            {"id": "recon", "role": "worker", "kind": "recon", "name": "信息收集员"},
            {"id": "expert-web", "role": "worker", "kind": "expert", "name": "Web 专家", "directions": ["web"]},
            {"id": "expert-reverse", "role": "worker", "kind": "expert", "name": "Reverse 专家", "directions": ["reverse"]},
            {"id": "harvest", "role": "worker", "kind": "harvest", "name": "知识收割员"},
            {"id": "reporter", "role": "worker", "kind": "reporter", "name": "报告收集员"}]
    events = []
    o = T.run_team(tools, "sys", "百万富翁", team=team, category="web", on_event=events.append,
                   ask_user=lambda q: f"题解……flag 是 {FLAG}")
    nodes = [e["node"] for e in events if e.get("type") == "role" and e["status"] == "start"]
    nudges = [e["text"] for e in events if e.get("type") == "guidance"]
    return o, nodes, nudges, state, len(plans)

o, nodes, nudges, state, nplans = run(False)
print("A nodes", nodes, "plans", nplans); print("A nudges", nudges)
print("A flag", o.result.flag, "cands", o.flags, "harvest", state.get("harvest"))
assert o.result.flag is None and o.flags == [], "user flag leaked"
assert "n3" in nodes and state.get("harvest"), "reverse expert / harvest missing"

o, nodes, nudges, state, nplans = run(True)
print("B nodes", nodes, "flag", o.result.flag, "cands", o.flags, "harvest", state.get("harvest"))
assert o.result.flag == FLAG and o.flags == [FLAG] and state.get("harvest")
print("PASS offline team test")
