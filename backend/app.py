"""FastAPI server for the Odele CTF console (frontend/backend split).

Exposes the session list, autosolve actions, and local configuration (platform tokens,
team mapping, model/provider settings) as REST, and pushes "changed" over WebSocket.
The heavy logic lives in backend.controller (autosolve/retry) and backend.manager
(sessions); this file is a thin HTTP layer. Configuration is stored in the DB
(backend.settings) and editable from the Settings / Team pages.

Run:  python -m backend.app        (or: uvicorn backend.app:app --reload)
"""

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.controller import Controller
from backend.manager import Manager, Session
from backend.settings import apply_model_settings, settings
from backend.team import load_team, save_team

manager = Manager()
controller = Controller(manager)
# Stored provider settings (model / API base / key) take over from .env at startup;
# workers spawned later inherit them through the environment.
apply_model_settings(settings)


# ---- background loop: advance the autosolve controller ---------------------
def _run_loop() -> None:
    while True:
        controller.step()
        time.sleep(0.5)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    threading.Thread(target=_run_loop, daemon=True).start()
    yield


app = FastAPI(title="Odele", lifespan=_lifespan)


def _fmt_time(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def session_to_dict(s: Session) -> dict:
    st = s.state
    return {
        "id": s.id,
        "title": s.title,
        "category": s.category,
        "status": st.get("status"),
        "flag": st.get("flag"),
        "created_at": _fmt_time(s.created_at),
        "created_ts": s.created_at or 0,
        "is_running": s.is_running(),
        "tool_calls": st.get("tool_calls", 0),
        "pending_approvals": sum(
            1 for a in (st.get("approvals") or []) if a.get("status") == "pending"
        ),
        "pending_mentions": sum(
            1 for m in (st.get("mentions") or []) if m.get("status") == "pending"
        ),
    }


def session_detail_to_dict(s: Session) -> dict:
    d = session_to_dict(s)
    st = s.state
    d.update({
        "replies": st.get("replies", 0),
        "thinking": st.get("thinking", ""),
        "paths": st.get("paths", []),
        "tools_used": st.get("tools_used", {}),
        "writeup": st.get("writeup", ""),
        "roles": st.get("roles", []),
        "approvals": st.get("approvals", []),
        "messages": st.get("messages", []),
        "mentions": st.get("mentions", []),
        "transcript": s.transcript,
    })
    return d


# ---- REST ------------------------------------------------------------------
@app.get("/api/status")
def status():
    return {"is_autosolving": controller.is_autosolving(), "version": controller.version}


@app.get("/api/sessions")
def list_sessions():
    return [session_to_dict(s) for s in manager.sessions]


@app.get("/api/sessions/{session_id}")
def get_session(session_id: int):
    s = controller.get_session(session_id)
    if s is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return session_detail_to_dict(s)


class StartAutosolve(BaseModel):
    directions: list[str]
    max: int = 3
    difficulty: str | None = None
    tokens: list[int] | None = None


@app.post("/api/autosolve/start")
def start_autosolve(body: StartAutosolve):
    err = controller.start_autosolve(body.directions, body.max, body.difficulty, body.tokens)
    if err:
        return JSONResponse({"error": err}, status_code=400)
    return {"ok": True}


@app.post("/api/autosolve/stop")
def stop_autosolve():
    controller.stop_autosolve()
    return {"ok": True}


@app.post("/api/sessions/{session_id}/stop")
def stop_session(session_id: int):
    controller.stop_session(session_id)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/delete")
def delete_session(session_id: int):
    controller.delete_session(session_id)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/guidance")
def send_guidance(session_id: int, body: dict):
    text = str(body.get("text") or "")
    if not text.strip():
        return JSONResponse({"error": "text is required"}, status_code=400)
    if not controller.guidance_session(session_id, text):
        return JSONResponse({"error": "session not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/reply")
def reply_session(session_id: int, body: dict):
    text = str(body.get("text") or "")
    if not text.strip():
        return JSONResponse({"error": "text is required"}, status_code=400)
    if not controller.reply_session(session_id, text):
        return JSONResponse({"error": "session not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/approve")
def approve_session(session_id: int, body: dict):
    node = str(body.get("node") or "").strip()
    if not node:
        return JSONResponse({"error": "node is required"}, status_code=400)
    if not controller.approve_session(session_id, node, bool(body.get("approved"))):
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/sessions/{session_id}/retry")
def retry_session(session_id: int):
    ok = controller.retry_session(session_id)
    if not ok:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"ok": True}


@app.post("/api/sessions/batch_delete")
def batch_delete():
    n = controller.batch_delete()
    return {"deleted": n}


@app.get("/api/config")
def config():
    return controller.config()


class ModelConfig(BaseModel):
    model: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    api_timeout: float | None = None


@app.put("/api/config")
def update_config(body: ModelConfig):
    settings.update_model(body.model_dump())
    apply_model_settings(settings)
    controller.notify_changed()
    return controller.config()


@app.get("/api/tokens")
def list_tokens():
    return {"tokens": settings.token_hints()}


@app.post("/api/tokens")
def add_token(body: dict):
    token = str(body.get("token") or "").strip()
    if not token:
        return JSONResponse({"error": "token is required"}, status_code=400)
    if len(settings.tokens()) >= 16:
        return JSONResponse({"error": "最多配置 16 个 token"}, status_code=400)
    settings.add_token(token)
    controller.notify_changed()
    return {"tokens": settings.token_hints()}


@app.delete("/api/tokens/{index}")
def delete_token(index: int):
    settings.remove_token(index)
    controller.notify_changed()
    return {"tokens": settings.token_hints()}


@app.post("/api/config/clear_failed")
def clear_failed():
    n = controller.clear_failed()
    return {"cleared": n}


@app.post("/api/manual")
def manual_solve(body: dict):
    spec = body.get("spec") or {}
    title = str(body.get("title") or spec.get("category") or "manual")
    session_id = controller.manual_solve(spec, title)
    return {"id": session_id}


@app.get("/api/autosolve/slots")
def autosolve_slots():
    return controller.autosolve_slots()


@app.get("/api/team")
def get_team():
    return {"members": load_team()}


@app.post("/api/team")
def set_team(body: dict):
    members = body.get("members")
    if not isinstance(members, list):
        return JSONResponse({"error": "members must be a list"}, status_code=400)
    saved = save_team(members)
    if not saved:
        return JSONResponse({"error": "没有有效成员（role 需为 lead/recon/expert/reporter）"},
                            status_code=400)
    controller.notify_changed()
    return {"ok": True, "count": saved}


@app.get("/api/team/skills")
def team_skills():
    from agent.skills import resolve
    out = []
    for index, member in enumerate(load_team()):
        items = resolve(member.get("skills") or [])
        out.append({
            "index": index,
            "id": member.get("id"),
            "role": member.get("role"),
            "name": member.get("name"),
            "description": member.get("description") or "",
            "directions": member.get("directions") or [],
            "skills": member.get("skills") or [],
            "skill_names": [item["name"] for item in items],
            "mcp": member.get("mcp") or [],
            "count": len(items),
            "entries": [
                {"index": i, "name": item["name"], "description": item["description"],
                 "kind": item["kind"], "file": item["path"].name}
                for i, item in enumerate(items)
            ],
        })
    return {"members": out}


@app.get("/api/skills/{skill_id}")
def library_skill_content(skill_id: str):
    import agent.skills as skills
    entry = next((e for e in skills.entries() if e["id"] == skill_id), None)
    if entry is None:
        return JSONResponse({"error": "skill not found"}, status_code=404)
    return {
        "id": entry["id"],
        "name": entry["name"],
        "description": entry["description"],
        "tags": entry["tags"],
        "kind": entry["kind"],
        "source": entry["path"].name,
        "content": skills.read(entry),
    }


@app.get("/api/team/skills/{member_index}/{entry_index}")
def team_skill_content(member_index: int, entry_index: int):
    import agent.skills as skills
    team = load_team()
    if not (0 <= member_index < len(team)):
        return JSONResponse({"error": "member not found"}, status_code=404)
    member = team[member_index]
    items = skills.resolve(member.get("skills") or [])
    if not (0 <= entry_index < len(items)):
        return JSONResponse({"error": "skill not found"}, status_code=404)
    item = items[entry_index]
    try:
        relative = item["path"].relative_to(skills.ROOT)
    except ValueError:
        relative = item["path"].name
    return {
        "name": item["name"],
        "description": item["description"],
        "kind": item["kind"],
        "source": str(relative),
        "content": skills.read(item),
    }


@app.get("/api/team/packs")
def team_packs():
    from agent.skills import available, tags
    return {"packs": available(), "tags": tags()}


@app.post("/api/team/roles")
def create_team_role(body: dict):
    from backend.team import create_role
    name = str(body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)
    skills = body.get("skills")
    if skills is not None and not isinstance(skills, list):
        return JSONResponse({"error": "skills must be a list"}, status_code=400)
    try:
        member = create_role(name, str(body.get("description") or ""), skills)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    controller.notify_changed()
    return {"member": member, "members": load_team()}


@app.delete("/api/team/roles/{member_id}")
def delete_team_role(member_id: str):
    from backend.team import delete_role
    if not delete_role(member_id):
        return JSONResponse({"error": "role not found"}, status_code=404)
    controller.notify_changed()
    return {"ok": True, "members": load_team()}


# ---- WebSocket ------------------------------------------------------------
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    last = controller.version
    try:
        while True:
            if controller.version != last:
                last = controller.version
                await websocket.send_json({"type": "changed"})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
