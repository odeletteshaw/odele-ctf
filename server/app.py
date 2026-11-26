"""FastAPI server for the Odele CTF console (frontend/backend split).

Exposes the session list + autosolve actions as REST, pushes "changed" over
WebSocket, and serves the static web frontend. The heavy logic lives in
server/controller.py (which wraps gui.manager.Manager); this file is a thin HTTP
layer.

Run:  python -m server.app        (or: uvicorn server.app:app --reload)
"""

import asyncio
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from gui.manager import Manager, Session
from server.controller import Controller

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

manager = Manager()
controller = Controller(manager)

app = FastAPI(title="Odele")


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
        "is_running": s.is_running(),
        "tool_calls": st.get("tool_calls", 0),
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
        "transcript": s.transcript,
    })
    return d


# ---- background loop: advance the autosolve controller ---------------------
def _run_loop() -> None:
    while True:
        controller.step()
        time.sleep(0.5)


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=_run_loop, daemon=True).start()


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


@app.post("/api/autosolve/start")
def start_autosolve(body: StartAutosolve):
    err = controller.start_autosolve(body.directions, body.max, body.difficulty)
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


@app.get("/api/memories")
def list_memories():
    return manager.list_memories()


@app.get("/api/memories/search")
def search_memories(q: str = ""):
    return manager.search_memories(q)


@app.get("/api/config")
def config():
    return controller.config()


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
    from core.team import load_team
    return {"members": load_team()}


@app.post("/api/team")
def set_team(body: dict):
    from core.team import save_team
    members = body.get("members")
    if not isinstance(members, list):
        return JSONResponse({"error": "members must be a list"}, status_code=400)
    save_team(members)
    return {"ok": True}


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


# ---- static frontend -------------------------------------------------------
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
