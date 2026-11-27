"""Backend orchestration: autosolve + session actions + retry, framework-agnostic.

The FastAPI app (backend.app) drives this single Controller, so the
agent logic lives in exactly one place. No UI imports here — user-facing confirmations
are the caller's job; this class just does the work and notifies listeners on change.
"""

import queue
import threading
import time
from typing import Any, Callable

from backend.autosolve import PLATFORM_CATEGORY, prepare_challenge
from backend.manager import Manager, Session
from backend.platform import PlatformClient, PlatformError, list_tokens
from backend.settings import mask_secret, settings
from backend.team import load_team

FAILED_STATUSES = ("done", "failed", "error", "cancelled")
ALREADY_SOLVED = "ALREADY_SOLVED"


class Controller:
    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self._auto_slots: list[dict[str, Any]] = []
        self._retry_queue: queue.Queue = queue.Queue()
        self._retry_submits: dict[int, dict] = {}
        self._version = 0
        self._listeners: list[Callable[[], None]] = []

    # ---- change notification ---------------------------------------------
    def on_change(self, cb: Callable[[], None]) -> None:
        self._listeners.append(cb)

    def _bump(self) -> None:
        self._version += 1
        for cb in self._listeners:
            try:
                cb()
            except Exception:
                pass

    @property
    def version(self) -> int:
        return self._version

    # ---- state queries ----------------------------------------------------
    def list_sessions(self) -> list[Session]:
        return self.manager.sessions

    def get_session(self, session_id: int) -> Session | None:
        for s in self.manager.sessions:
            if s.id == session_id:
                self.manager.load_transcript(s)
                return s
        return None

    def is_autosolving(self) -> bool:
        return any(s["running"] for s in self._auto_slots)

    # ---- actions ----------------------------------------------------------
    def start_autosolve(self, directions: list[str], maxn: int, diff: str | None,
                        token_indices: list[int] | None = None) -> str | None:
        """Start autosolve. `token_indices` picks which platform tokens this run may use;
        directions are spread round-robin across the selected tokens."""
        tokens = list_tokens()
        if not tokens:
            return "没有 token（在配置页添加 CTF2 agent token）"
        selected: list[int] = []
        for index in token_indices or []:
            if isinstance(index, int) and 0 <= index < len(tokens) and index not in selected:
                selected.append(index)
        if not selected:
            selected = list(range(len(tokens)))
        self._auto_slots = []
        persisted_failed = self.manager.failed_ids()
        for position, direction in enumerate(directions):
            ti = selected[position % len(selected)]
            self._auto_slots.append({
                "running": True, "direction": direction, "token": tokens[ti],
                "tokens": tokens, "token_index": ti,
                "max": maxn, "difficulty": diff, "done": 0,
                "failed": set(persisted_failed),
                "current": None, "current_meta": None, "phase": "idle", "queue": queue.Queue(),
            })
        self._bump()
        return None

    def stop_autosolve(self) -> None:
        for s in self._auto_slots:
            s["running"] = False
        self._auto_slots = []
        self._bump()

    def stop_session(self, session_id: int) -> None:
        s = self.get_session(session_id)
        if s and s.is_running():
            self.manager.stop(s)
            self._bump()

    def set_writeup(self, session_id: int, text: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        session.state["writeup"] = text
        self.manager.save()
        self._bump()
        return True

    def guidance_session(self, session_id: int, text: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        text = text.strip()
        if not text:
            return False
        if session.is_running():
            # Live run: inject as supervisor guidance the worker will pick up.
            session.send_guidance(text)
            session.state.setdefault("messages", []).append({
                "from": "你", "to": "团队", "kind": "user", "node": None, "text": text,
            })
            session.state["messages"] = session.state["messages"][-200:]
            self.manager.save()
            self._bump()
            return True
        # Finished run: the worker is gone, so a message can't reach it. Treat it as "here's
        # a writeup/hint, keep going" — re-launch the solve with the user's info appended as
        # context so the team replans from it (and still reproduces the flag with its tools).
        spec = dict(session.spec or {})
        prior = str(spec.get("context") or "")
        spec["context"] = (prior + "\n\n" if prior else "") + f"[用户补充] {text}"
        spec.setdefault("team", load_team())
        session.reset(spec)
        session.state.setdefault("messages", []).append({
            "from": "你", "to": "团队", "kind": "user", "node": None, "text": text,
        })
        session.start()
        self.manager.save()
        self._bump()
        return True

    def reply_session(self, session_id: int, text: str) -> bool:
        session = self.get_session(session_id)
        if session is None:
            return False
        text = text.strip()
        if not text:
            return False
        session.reply(text)
        session.state.setdefault("messages", []).append({
            "from": "你", "to": "团队", "kind": "user", "node": None, "text": text,
        })
        session.state["messages"] = session.state["messages"][-200:]
        self.manager.save()
        self._bump()
        return True

    def approve_session(self, session_id: int, node: str, approved: bool) -> bool:
        """Resolve a DAG-node approval request from the console."""
        session = self.get_session(session_id)
        if session is None:
            return False
        session.approve(node, approved)
        self._bump()
        return True

    def delete_session(self, session_id: int) -> None:
        s = self.get_session(session_id)
        if s:
            self.manager.delete(s)
            self._bump()

    def batch_delete(self) -> int:
        doomed = [s for s in self.manager.sessions if s.state["status"] in FAILED_STATUSES]
        for s in doomed:
            self.manager.delete(s)
        if doomed:
            self._bump()
        return len(doomed)

    def retry_session(self, session_id: int) -> bool:
        s = self.get_session(session_id)
        if not s:
            return False
        # mark "preparing" immediately so the UI reflects the retry during the fetch phase
        s.state["status"] = "preparing"
        s.state["done"] = False
        self.manager.save()
        self._bump()
        threading.Thread(target=self._retry_worker, args=(s,), daemon=True).start()
        return True

    def manual_solve(self, spec: dict, title: str) -> int:
        spec = dict(spec)
        spec["manual"] = True  # explicit marker: filed under the 手动解题 page
        spec.setdefault("team", load_team())
        session = self.manager.new_session(spec, title, spec.get("category", "web"))
        self._bump()
        return session.id

    def config(self) -> dict:
        model = settings.model_config()
        return {
            "model": model["model"],
            "api_base": model["api_base"],
            "api_key": mask_secret(model["api_key"]) or "未设置",
            "api_timeout": model["api_timeout"],
            "token_count": len(settings.tokens()),
            "token_hints": settings.token_hints(),
            "failed_count": len(self.manager.failed_ids()),
            "memory_count": len(self.manager.list_memories()),
            "db_path": str(settings.path),
        }

    def notify_changed(self) -> None:
        """Public hook, e.g. after settings are updated through the API."""
        self._bump()

    def clear_failed(self) -> int:
        n = len(self.manager.failed_ids())
        self.manager.clear_failed()
        self._bump()
        return n

    def autosolve_slots(self) -> list[dict]:
        """Describe the active autosolve slots for the multi-agent view."""
        out = []
        for s in self._auto_slots:
            out.append({
                "direction": s["direction"],
                "token_index": s["token_index"],
                "running": s["running"],
                "phase": s["phase"],
                "done": s["done"],
                "current_title": s["current"].title if s["current"] else None,
            })
        return out

    # ---- driving loop (call periodically) ---------------------------------
    def step(self) -> None:
        try:
            self.manager.drain_all()
            self._drain_retry_queue()
            self._check_retry_submits()
            self._autosolve_step()
        except Exception:
            import traceback
            traceback.print_exc()

    def shutdown(self) -> None:
        self.stop_autosolve()
        self.manager.stop_all()

    # ---- retry ------------------------------------------------------------
    def _retry_worker(self, session: Session) -> None:
        # Transient SSL/network blips are common; retry the fetch a few times with backoff.
        for attempt in range(3):
            try:
                spec = session.spec or {}
                cid = spec.get("platform_challenge_id")
                gid = spec.get("platform_ground_id")
                if not cid or not gid:
                    resolved = self._resolve_platform_id(session.title, session.category)
                    if resolved is None:
                        self._retry_queue.put(("error", session,
                            f"{session.title}: 找不到平台题目信息（可能已解，或不在任何 token 的未解队列）"))
                        return
                    cid, gid = resolved
                client = PlatformClient()
                try:
                    item = {"id": cid, "practice_ground_id": gid,
                            "category": str(session.category).upper(), "name": session.title}
                    new_spec, meta = prepare_challenge(client, item)
                    new_spec = dict(new_spec)
                    new_spec["platform_challenge_id"] = cid
                    new_spec["platform_ground_id"] = gid
                    new_spec.setdefault("team", load_team())
                    self._retry_queue.put(("spec", new_spec, meta, str(cid), session))
                finally:
                    client.close()
                return  # success
            except Exception as e:
                if attempt == 2:
                    self._retry_queue.put(("error", session, f"{session.title}: {e}"))
                    return
                time.sleep(5 * (attempt + 1))

    def _resolve_platform_id(self, title: str, category: str) -> tuple[str, str] | None:
        for tok in list_tokens():
            client = PlatformClient(token=tok)
            try:
                nc = client.next_challenges(limit=200, category=PLATFORM_CATEGORY.get(category))
                items = nc.get("items") or []
                for it in items:
                    if str(it.get("name")) == title:
                        return (str(it.get("id")), str(it.get("practice_ground_id")))
            except Exception:
                pass  # try the next token
            finally:
                client.close()
        return None

    def _drain_retry_queue(self) -> None:
        while True:
            try:
                item = self._retry_queue.get_nowait()
            except queue.Empty:
                break
            kind = item[0] if isinstance(item, tuple) else None
            if kind == "spec" and len(item) >= 5:
                spec, meta, cid, session = item[1], item[2], item[3], item[4]
                self.manager.remove_failed(cid)
                session.reset(spec)   # reuse the same record (same id)
                session.start()
                self.manager.save()
                self._retry_submits[session.id] = meta
            elif kind == "error" and len(item) >= 3:
                session, msg = item[1], item[2]
                print(f"[retry] {msg}")
                if session.state["status"] == "preparing":
                    session.state["status"] = "error"
                    session.state["done"] = True
                    session.transcript.append({"type": "status", "status": "error", "error": msg})
                    self.manager.save()
            self._bump()

    def _check_retry_submits(self) -> None:
        for sid, meta in list(self._retry_submits.items()):
            session = next((s for s in self.manager.sessions if s.id == sid), None)
            if session is None:
                self._retry_submits.pop(sid, None)
                continue
            if not session.state["done"]:
                continue
            self._retry_submits.pop(sid, None)
            flag = session.state.get("flag")
            threading.Thread(target=self._finalize_retry,
                             args=(meta, flag, session), daemon=True).start()

    def _finalize_retry(self, meta: dict, flag: str | None,
                        session: Session | None = None) -> None:
        accepted = None
        already_solved = False
        candidates: list[str] = []
        if session is not None:
            candidates.extend(session.state.get("flag_candidates") or [])
        if flag and flag not in candidates:
            candidates.insert(0, flag)
        try:
            client = PlatformClient()
            try:
                for candidate in dict.fromkeys(candidates):
                    try:
                        response = client.submit_flag(meta["ground_id"], meta["challenge_id"], candidate)
                    except PlatformError as e:
                        print(f"[retry submit] rejected: {candidate!r}: {e.code}")
                        if e.code == ALREADY_SOLVED:
                            # Every further candidate would get the same answer; stop
                            # instead of spraying the rest at the platform.
                            already_solved = True
                            break
                        continue
                    if isinstance(response, dict) and (
                            response.get("accepted") or response.get("is_solved")):
                        accepted = candidate
                        break
                    if self._challenge_solved(client, meta):
                        accepted = candidate
                        break
                client.log_note(meta["challenge_id"], "result",
                                (f"solved: {accepted}" if accepted else "no accepted flag")[:2000])
            finally:
                try:
                    client.delete_environment(meta["ground_id"], meta["challenge_id"])
                except Exception:
                    pass
                client.close()
        except Exception as e:
            print(f"[retry] finalize: {e}")
        if session is not None:
            if accepted:
                session.state["status"] = "solved"
                session.state["flag"] = accepted
                session.state["done"] = True
                self.manager.save()
                self._bump()
                self._remember(session)
            elif already_solved:
                self._mark_already_solved(session, flag or (candidates[0] if candidates else None))
            else:
                session.state["status"] = "failed"
                session.state["flag"] = None
                session.state["done"] = True
                session.state.setdefault("messages", []).append({
                    "from": "平台", "to": "团队", "kind": "submit",
                    "text": "平台未确认该 flag，任务已标记为失败",
                })
                self.manager.save()
                self._bump()

    # ---- autosolve control loop -------------------------------------------
    def _autosolve_step(self) -> None:
        for slot in list(self._auto_slots):
            if not slot["running"]:
                continue
            self._step_slot(slot)

    def _step_slot(self, slot: dict) -> None:
        if slot["phase"] == "idle":
            slot["phase"] = "preparing"
            threading.Thread(target=self._autosolve_worker, args=(slot,), daemon=True).start()
        elif slot["phase"] == "preparing":
            try:
                result = slot["queue"].get_nowait()
            except queue.Empty:
                return
            kind = result[0] if isinstance(result, tuple) else None
            if kind == "placeholder":
                meta = result[1]
                pending = self.manager.new_pending_session(
                    {"kind": "custom", "category": slot["direction"], "urls": [],
                     "description": "", "attachments": [], "flag_prefix": "flag"},
                    meta["name"], slot["direction"])
                slot["pending"] = pending
            elif kind == "spec":
                spec, meta = result[1]
                spec = dict(spec)
                spec["platform_challenge_id"] = meta["challenge_id"]
                spec["platform_ground_id"] = meta["ground_id"]
                spec.setdefault("team", load_team())
                pending = slot.get("pending")
                if pending is not None:
                    self.manager.start_pending_session(pending, spec)
                    slot["pending"] = None
                    slot["current"] = pending
                    slot["current_meta"] = meta
                else:
                    session = self.manager.new_session(spec, meta["name"], meta["category"])
                    slot["current"] = session
                    slot["current_meta"] = meta
                slot["phase"] = "solving"
            else:
                skip = kind == "error" and isinstance(result, tuple) and len(result) >= 3
                if skip:
                    item, msg = result[1], result[2]
                    slot.setdefault("failed", set()).add(str(item.get("id")))
                    self.manager.add_failed(str(item.get("id")), slot["direction"])
                else:
                    msg = result[1] if isinstance(result, tuple) else "打题结束"
                pending = slot.get("pending")
                if pending is not None:
                    pending.state["status"] = "error"
                    pending.state["done"] = True
                    pending.transcript.append({"type": "status", "status": "error", "error": msg})
                    slot["pending"] = None
                    self.manager.save()
                if skip:
                    print(f"[autosolve:{slot['direction']}] skip: {msg}")
                    slot["phase"] = "idle"
                else:
                    self._stop_slot(slot, msg)
        elif slot["phase"] == "solving":
            session = slot["current"]
            if session is not None and session.state["done"]:
                self._submit_slot(slot)

    def _autosolve_worker(self, slot: dict) -> None:
        try:
            client = PlatformClient(token=slot["token"])
            try:
                nc = client.next_challenges(
                    limit=50, category=PLATFORM_CATEGORY.get(slot["direction"]),
                    difficulty=slot.get("difficulty"),
                )
                items = nc.get("items") or []
                failed = slot.get("failed") or set()
                item = next((it for it in items
                             if str(it.get("category", "")).lower() == slot["direction"]
                             and str(it.get("id")) not in failed), None)
                if item is None:
                    slot["queue"].put(("stop", f"{slot['direction']} 没有未解的题了"))
                    return
                slot["queue"].put(("placeholder", {"name": item.get("name") or slot["direction"]}))
                try:
                    result = prepare_challenge(client, item)
                except Exception as e:
                    slot["queue"].put(("error", item, f"{item.get('name')}: {e}"))
                    return
                if result is None:
                    slot["queue"].put(("stop", f"{slot['direction']} 不支持"))
                    return
                slot["queue"].put(("spec", result))
            finally:
                client.close()
        except Exception as e:
            slot["queue"].put(("error", str(e)))

    def _submit_slot(self, slot: dict) -> None:
        session = slot["current"]
        meta = slot["current_meta"]
        slot["current"] = None
        slot["current_meta"] = None
        client = PlatformClient(token=slot["token"])
        try:
            flag = session.state.get("flag") if session else None
            candidates: list[str] = []
            if session is not None:
                candidates.extend(session.state.get("flag_candidates") or [])
            if flag and flag not in candidates:
                candidates.insert(0, flag)
            solved = False
            accepted = None
            submit_error = None
            already_solved = False
            try:
                for candidate in dict.fromkeys(candidates):
                    try:
                        response = client.submit_flag(meta["ground_id"], meta["challenge_id"], candidate)
                    except PlatformError as e:
                        submit_error = e.code
                        print(f"[autosolve:{slot['direction']}] submit rejected: {candidate!r}: {e.code}")
                        if e.code == ALREADY_SOLVED:
                            already_solved = True
                            break
                        continue
                    except Exception as e:
                        print(f"[autosolve:{slot['direction']}] submit error: {candidate!r}: {e}")
                        continue
                    # The submit response is the platform's direct verdict; is_solved can
                    # lag behind it. Trust either, so a valid flag is not discarded.
                    if isinstance(response, dict) and (
                            response.get("accepted") or response.get("is_solved")):
                        solved = True
                        accepted = candidate
                        break
                    if self._challenge_solved(client, meta):
                        solved = True
                        accepted = candidate
                        break
                client.log_note(meta["challenge_id"], "result",
                                (f"solved: {accepted}" if accepted else "no accepted flag")[:2000])
            except Exception as e:
                print(f"[autosolve:{slot['direction']}] submit/note error: {e}")
            try:
                client.delete_environment(meta["ground_id"], meta["challenge_id"])
            except Exception as e:
                print(f"[autosolve:{slot['direction']}] delete env error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass
        if accepted and solved:
            slot["done"] += 1
            if session is not None:
                session.state["status"] = "solved"
                session.state["flag"] = accepted
            self._remember(session)
        elif already_solved and session is not None:
            self._mark_already_solved(session, flag or (candidates[0] if candidates else None))
        else:
            cid = str(meta["challenge_id"])
            slot.setdefault("failed", set()).add(cid)
            self.manager.add_failed(cid, slot["direction"])
            # The worker reports "solved" as soon as any flag-shaped string appears;
            # only the platform can confirm it. Correct a rejected/decoys flag here so
            # the UI never claims a success the platform did not record.
            if session is not None:
                session.state["status"] = "failed"
                session.state["flag"] = None
                session.state["done"] = True
                note = "平台未确认解题成功" + (f"（{submit_error}）" if submit_error else "")
                session.state.setdefault("messages", []).append({
                    "from": "平台", "to": "团队", "kind": "submit", "text": note,
                })
                self.manager.save()
        if slot["max"] and slot["done"] >= slot["max"]:
            self._stop_slot(slot, f"{slot['direction']} 已解出上限（{slot['done']} 道）")
        else:
            slot["phase"] = "idle"
        self._bump()

    def _mark_already_solved(self, session: Session, flag: str | None) -> None:
        """The account solved this challenge before, so the platform answers every submit
        with ALREADY_SOLVED. That is not a failure: keep the run's own best candidate and
        say plainly that this run's flag could not be checked."""
        session.state["status"] = "solved"
        session.state["flag"] = flag
        session.state["done"] = True
        session.state.setdefault("messages", []).append({
            "from": "平台", "to": "团队", "kind": "submit", "text": "平台显示该题此前已解（ALREADY_SOLVED），无法单独校验本次 flag；已停止继续提交其它候选",
        })
        self.manager.save()
        self._bump()

    def _challenge_solved(self, client, meta: dict) -> bool:
        try:
            ch = client.get_challenge(meta["ground_id"], meta["challenge_id"])
            return bool(ch.get("is_solved"))
        except Exception:
            return False

    def _remember(self, session: Session) -> None:
        """Record a solved challenge in the memory pool so future challenges can reuse it."""
        writeup = (session.state.get("writeup") or "").strip()
        title = (session.title or "").strip()
        if not writeup and not title:
            return
        content = f"题目: {title}\n方向: {session.category}\n\n{writeup}".strip()
        try:
            self.manager.add_memory(session.category, title, content, "solve")
        except Exception as e:
            print(f"[memory] {e}")

    def _stop_slot(self, slot: dict, msg: str) -> None:
        slot["running"] = False
        slot["phase"] = "idle"
        slot["current"] = None
        slot["current_meta"] = None
        print(f"[autosolve:{slot['direction']}] {msg}")
