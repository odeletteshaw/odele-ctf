"""Odele supervision console (view layer).

Layout: a fixed 3:7 split — a slim sidebar (brand + navigation) on the left, and a
single main content area on the right that swaps between three pages:

  - CTF 打题   : a table of all sessions (category / title / status / actions) with a
                 search box, "开始打题", and "批量删除".
  - 手动解题   : a form to launch a custom target by hand (for hard challenges you want
                 to steer yourself).
  - 配置管理   : read-only view of the model / API / token configuration.

The conversation transcript is still recorded (in SQLite) but is intentionally NOT shown;
only a compact detail popup with the outcome (flag, findings, tool counts, writeup) is
available via "查看". All agent logic lives in the Session subprocess (gui/worker.py) and
the Manager (gui/manager.py); this module only renders and drives them.
"""

import queue
import signal
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path
from typing import Any

import customtkinter as ctk

from .manager import Manager, Session

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

VERSION = "0.3.0"

# --- palette ---------------------------------------------------------------
FG = "#d6dae3"
MUTED = "#7f8a9b"
SIDEBAR_BG = "#141a24"
PAGE_BG = "#0f1218"
CARD_BG = "#171d29"
ACCENT = "#243043"
DANGER = "#5a2b2b"
DANGER_HOVER = "#703636"

STATUS_LABEL = {
    "running": "进行中",
    "preparing": "准备中",
    "solved": "已解",
    "done": "失败",
    "failed": "失败",
    "error": "错误",
    "cancelled": "已停止",
    "idle": "待命",
}
STATUS_COLOR = {
    "running": "#ffd166",
    "preparing": "#8b94a7",
    "solved": "#79d98a",
    "done": "#ff6b6b",
    "failed": "#ff6b6b",
    "error": "#ff6b6b",
    "cancelled": "#c98a3d",
    "idle": "#8b94a7",
}
# status filter bucket -> the statuses it matches
STATUS_GROUPS = {
    "进行中": {"running", "preparing", "idle"},
    "失败": {"failed", "error", "cancelled", "done"},
    "已解": {"solved"},
}

PAGE_SIZE = 10  # table rows per page


class ConsoleApp:
    def __init__(self, manager: Manager, poll_ms: int = 150) -> None:
        self.manager = manager
        self.poll_ms = poll_ms
        self._auto_slots: list[dict[str, Any]] = []
        self._retry_queue: queue.Queue = queue.Queue()
        self._search_text = ""
        self._status_filter = "全部"
        self._page = 0
        self._table_sig: tuple | None = None
        self._manual_attachments: list[str] = []

        self.root = ctk.CTk()
        self.root.title(f"Odele v{VERSION}")
        self.root.geometry("1280x800")
        self.mono = ctk.CTkFont(family="Menlo", size=13)
        self.mono_s = ctk.CTkFont(family="Menlo", size=11)
        self.bold = ctk.CTkFont(family="Menlo", size=16, weight="bold")
        self.bold_s = ctk.CTkFont(family="Menlo", size=12, weight="bold")

        self._build()
        self._install_signal_handlers()
        self._show_page("ctf")
        self.root.after(self.poll_ms, self._poll)
        self.root.after(1000, self._refresh_table_loop)

    # =====================================================================
    #  layout
    # =====================================================================
    def _build(self) -> None:
        # fixed 3:7 split, non-draggable (plain grid, no paned window)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=3)
        self.root.grid_columnconfigure(1, weight=7)
        self._build_sidebar()
        self._build_pages()

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self.root, fg_color=SIDEBAR_BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(26, 18))
        ctk.CTkLabel(brand, text="Odele", font=self.bold, text_color=FG).pack(anchor="w")
        ctk.CTkLabel(brand, text=f"v{VERSION}", font=self.mono_s, text_color=MUTED).pack(anchor="w")

        self._menu_btns: dict[str, ctk.CTkButton] = {}
        for key, label in (("ctf", "CTF 打题"), ("manual", "手动解题"), ("config", "配置管理")):
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w", height=42,
                fg_color="transparent", hover_color=ACCENT,
                command=lambda k=key: self._show_page(k),
            )
            btn.pack(fill="x", padx=12, pady=4)
            self._menu_btns[key] = btn

    def _build_pages(self) -> None:
        self.main = ctk.CTkFrame(self.root, fg_color=PAGE_BG, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(0, weight=1)
        self.main.grid_columnconfigure(0, weight=1)
        self.pages: dict[str, ctk.CTkFrame] = {
            "ctf": self._build_ctf_page(),
            "manual": self._build_manual_page(),
            "config": self._build_config_page(),
        }

    def _show_page(self, name: str) -> None:
        for key, page in self.pages.items():
            page.grid_remove()
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        for key, btn in self._menu_btns.items():
            btn.configure(fg_color=ACCENT if key == name else "transparent")
        if name == "ctf":
            self._page = 0
            self._table_sig = None  # force a refresh on switch
            self._render_table()

    def add_session(self, session: Session) -> None:
        """Expose a just-created session (used by gui.launch's CLI args)."""
        self._table_sig = None
        self._show_page("ctf")

    # =====================================================================
    #  page: CTF 打题
    # =====================================================================
    def _build_ctf_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.main, fg_color="transparent")
        page.grid_rowconfigure(2, weight=1)
        page.grid_columnconfigure(0, weight=1)

        # toolbar
        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        self.btn_auto = ctk.CTkButton(bar, text="▶ 开始打题", height=38, width=130,
                                      command=self._toggle_autosolve)
        self.btn_auto.pack(side="left")
        ctk.CTkButton(bar, text="🗑 批量删除", height=38, width=120,
                      fg_color=DANGER, hover_color=DANGER_HOVER,
                      command=self._batch_delete).pack(side="left", padx=(8, 0))
        self.table_search = ctk.CTkEntry(bar, placeholder_text="搜索大类 / 题目名称 / 状态…",
                                         height=38, font=self.mono)
        self.table_search.pack(side="left", padx=(28, 10), fill="x", expand=True)
        self.table_search.bind("<KeyRelease>", lambda _e: self._on_search())
        self.status_seg = ctk.CTkSegmentedButton(bar, values=["全部", "进行中", "失败", "已解"],
                                                 command=lambda _v: self._on_filter())
        self.status_seg.set("全部")
        self.status_seg.pack(side="left")

        # column header
        head = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=0)
        head.grid(row=1, column=0, sticky="ew", padx=20)
        head.grid_columnconfigure(1, weight=1)
        for col, text, width in ((0, "大类", 90), (1, "题目名称", 0), (2, "状态", 90), (3, "操作", 232)):
            kwargs: dict[str, Any] = {"text": text, "font": self.bold_s, "text_color": MUTED}
            if width:
                kwargs["width"] = width
            lbl = ctk.CTkLabel(head, **kwargs)
            lbl.grid(row=0, column=col, padx=10, pady=9, sticky="w")

        # rows
        self.table_rows = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.table_rows.grid(row=2, column=0, sticky="nsew", padx=20, pady=(6, 4))
        # pagination bar (fixed at the bottom, outside the scroll area)
        self.page_bar = ctk.CTkFrame(page, fg_color="transparent")
        self.page_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))
        return page

    def _on_search(self) -> None:
        self._search_text = (self.table_search.get() or "").strip().lower()
        self._page = 0
        self._render_table()

    def _on_filter(self) -> None:
        self._status_filter = self.status_seg.get()
        self._page = 0
        self._render_table()

    def _visible_sessions(self) -> list[Session]:
        def matches(s: Session) -> bool:
            if self._search_text:
                hay = (f"{s.category} {s.title} "
                       f"{STATUS_LABEL.get(s.state['status'], s.state['status'])}").lower()
                if self._search_text not in hay:
                    return False
            if self._status_filter != "全部":
                if s.state["status"] not in STATUS_GROUPS.get(self._status_filter, ()):
                    return False
            return True

        def sort_key(s: Session) -> tuple:
            st = s.state["status"]
            if st in ("running", "preparing", "idle"):
                group = 0
            elif st in ("failed", "error", "cancelled", "done"):
                group = 1
            else:
                group = 2
            return (group, -s.id)

        return sorted((s for s in self.manager.sessions if matches(s)), key=sort_key)

    def _render_table(self) -> None:
        for child in self.table_rows.winfo_children():
            child.destroy()
        rows = self._visible_sessions()
        total = len(rows)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page = max(0, min(self._page, total_pages - 1))
        start = self._page * PAGE_SIZE
        for s in rows[start:start + PAGE_SIZE]:
            self._table_row(s)
        self._render_pagination(total, total_pages)

    def _render_pagination(self, total: int, total_pages: int) -> None:
        for child in self.page_bar.winfo_children():
            child.destroy()
        prev = ctk.CTkButton(self.page_bar, text="‹ 上一页", width=92, height=30,
                             font=self.mono_s, command=self._prev_page)
        prev.pack(side="left", padx=4)
        if self._page <= 0:
            prev.configure(state="disabled", fg_color="#2a2f3a")
        ctk.CTkLabel(self.page_bar, text=f"第 {self._page + 1} / {total_pages} 页 · 共 {total} 条",
                     font=self.mono_s, text_color=MUTED).pack(side="left", expand=True)
        nxt = ctk.CTkButton(self.page_bar, text="下一页 ›", width=92, height=30,
                            font=self.mono_s, command=self._next_page)
        nxt.pack(side="right", padx=4)
        if self._page >= total_pages - 1:
            nxt.configure(state="disabled", fg_color="#2a2f3a")

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render_table()

    def _next_page(self) -> None:
        self._page += 1
        self._render_table()

    def _table_row(self, session: Session) -> None:
        row = ctk.CTkFrame(self.table_rows, fg_color=CARD_BG, corner_radius=6)
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(1, weight=1)

        st = session.state["status"]
        cat = ctk.CTkLabel(row, text=session.category, width=90, anchor="w", font=self.mono_s,
                           text_color=MUTED)
        cat.grid(row=0, column=0, padx=10, pady=6, sticky="w")
        title = ctk.CTkLabel(row, text=session.title, anchor="w", font=self.mono, text_color=FG)
        title.grid(row=0, column=1, padx=10, sticky="ew")
        stat = ctk.CTkLabel(row, text=STATUS_LABEL.get(st, st), width=90,
                            text_color=STATUS_COLOR.get(st, FG), font=self.mono_s)
        stat.grid(row=0, column=2, padx=10)

        act = ctk.CTkFrame(row, fg_color="transparent")
        act.grid(row=0, column=3, padx=6, pady=2)
        ctk.CTkButton(act, text="查看", width=52, height=26, font=self.mono_s,
                      command=lambda s=session: self._view_detail(s)).pack(side="left", padx=2)
        if session.is_running():
            ctk.CTkButton(act, text="停止", width=52, height=26, font=self.mono_s,
                          fg_color=DANGER, hover_color=DANGER_HOVER,
                          command=lambda s=session: self._stop_session(s)).pack(side="left", padx=2)
        elif (session.spec.get("platform_challenge_id")
              and session.state["status"] in ("done", "failed", "error", "cancelled")):
            ctk.CTkButton(act, text="重试", width=52, height=26, font=self.mono_s,
                          fg_color="#2a3648", hover_color=ACCENT,
                          command=lambda s=session: self._retry_challenge(s)).pack(side="left", padx=2)
        ctk.CTkButton(act, text="删除", width=52, height=26, font=self.mono_s,
                      fg_color=DANGER, hover_color=DANGER_HOVER,
                      command=lambda s=session: self._delete_session(s)).pack(side="left", padx=2)

        # right-click anywhere on the row → copy menu (labels aren't selectable otherwise)
        for w in (row, cat, title, stat, act):
            w.bind("<Button-3>", lambda e, s=session: self._row_menu(e, s))

    def _row_menu(self, event: tk.Event, session: Session) -> None:
        menu = tk.Menu(self.root, tearoff=0, bg="#141822", fg=FG,
                       activebackground=ACCENT, activeforeground=FG)
        menu.add_command(label="复制题目名称", command=lambda: self._copy(session.title))
        flag = session.state.get("flag")
        if flag:
            menu.add_command(label="复制 FLAG", command=lambda: self._copy(flag))
        menu.tk_popup(event.x_root, event.y_root)

    def _copy(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    # ---- row actions -----------------------------------------------------
    def _view_detail(self, session: Session) -> None:
        self.manager.load_transcript(session)
        st = session.state
        paths = "\n".join(f"  - {p}" for p in (st.get("paths") or [])) or "—"
        tools = ", ".join(f"{k}×{v}" for k, v in (st.get("tools_used") or {}).items()) or "—"
        flag = st.get("flag") or "—"
        writeup = st.get("writeup") or "（未生成）"

        win = ctk.CTkToplevel(self.root)
        win.title(session.title)
        win.geometry("680x560")
        win.transient(self.root)
        win.grab_set()
        head = ctk.CTkLabel(win, text=f"{session.title}  ·  {session.category}", font=self.bold,
                            text_color=FG, anchor="w")
        head.pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(win, text=STATUS_LABEL.get(st["status"], st["status"]),
                     text_color=STATUS_COLOR.get(st["status"], FG), font=self.mono_s,
                     anchor="w").pack(fill="x", padx=20)
        flag_row = ctk.CTkFrame(win, fg_color="transparent")
        flag_row.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(flag_row, text=f"FLAG  {flag}", text_color="#79d98a", font=self.mono,
                     anchor="w", justify="left").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(flag_row, text="复制", width=56, height=26, font=self.mono_s,
                      command=lambda: self._copy(flag)).pack(side="right")

        box = ctk.CTkTextbox(win, font=self.mono_s, wrap="word")
        box.pack(fill="both", expand=True, padx=20, pady=12)
        box.insert("end", (
            f"replies: {st.get('replies', 0)}   tool calls: {st.get('tool_calls', 0)}\n"
            f"耗时: {session.elapsed():.0f}s   工具: {tools}\n\n"
            f"Findings:\n{paths}\n\n"
            f"题解:\n{writeup}\n"
        ))
        box.configure(state="disabled")

    def _stop_session(self, session: Session) -> None:
        if session.is_running():
            self.manager.stop(session)
            self._table_sig = None
            self._render_table()

    def _delete_session(self, session: Session) -> None:
        if not messagebox.askyesno("删除", f"删除 “{session.title}”？此操作不可撤销。",
                                   parent=self.root):
            return
        self.manager.delete(session)
        self._table_sig = None
        self._render_table()

    def _batch_delete(self) -> None:
        doomed = [s for s in self.manager.sessions
                  if s.state["status"] in ("done", "failed", "error", "cancelled")]
        if not doomed:
            messagebox.showinfo("批量删除", "没有失败的 session 可删。", parent=self.root)
            return
        if not messagebox.askyesno("批量删除", f"删除 {len(doomed)} 个失败的 session？",
                                   parent=self.root):
            return
        for s in doomed:
            self.manager.delete(s)
        self._table_sig = None
        self._render_table()

    def _retry_challenge(self, session: Session) -> None:
        """Retry ONE failed challenge: un-blacklist it and re-fetch + re-solve it."""
        spec = session.spec or {}
        cid = spec.get("platform_challenge_id")
        gid = spec.get("platform_ground_id")
        if not cid or not gid:
            messagebox.showinfo("重试", "这个 session 没有平台题目信息，无法自动重试。", parent=self.root)
            return
        if not messagebox.askyesno("重试", f"重新解 “{session.title}”？会重新起环境并重试一次。",
                                   parent=self.root):
            return
        self.manager.remove_failed(str(cid))
        threading.Thread(target=self._retry_worker,
                         args=(cid, gid, session.category, session.title), daemon=True).start()

    def _retry_worker(self, cid: str, gid: str, category: str, title: str) -> None:
        try:
            from core.autosolve import prepare_challenge
            from core.platform import PlatformClient
            client = PlatformClient()
            try:
                item = {"id": cid, "practice_ground_id": gid,
                        "category": str(category).upper(), "name": title}
                spec, meta = prepare_challenge(client, item)
                spec = dict(spec)
                spec["platform_challenge_id"] = cid
                spec["platform_ground_id"] = gid
                self._retry_queue.put(("spec", spec, meta))
            finally:
                client.close()
        except Exception as e:
            self._retry_queue.put(("error", f"{title}: {e}"))

    def _drain_retry_queue(self) -> None:
        while True:
            try:
                item = self._retry_queue.get_nowait()
            except queue.Empty:
                break
            kind = item[0] if isinstance(item, tuple) else None
            if kind == "spec" and len(item) >= 3:
                spec, meta = item[1], item[2]
                self.manager.new_session(spec, meta["name"], meta["category"])
            elif kind == "error":
                print(f"[retry] {item[1] if len(item) > 1 else 'error'}")
            self._table_sig = None

    # =====================================================================
    #  autosolve (unchanged control loop, re-homed to the new toolbar)
    # =====================================================================
    def _toggle_autosolve(self) -> None:
        if any(s["running"] for s in self._auto_slots):
            for s in self._auto_slots:
                s["running"] = False
            self._auto_slots = []
            self.btn_auto.configure(text="▶ 开始打题")
            return
        self._open_autosolve_dialog()

    def _open_autosolve_dialog(self) -> None:
        win = ctk.CTkToplevel(self.root)
        win.title("开始打题")
        win.geometry("420x360")
        win.transient(self.root)
        win.grab_set()

        ctk.CTkLabel(win, text="方向（多选）", font=self.bold_s, text_color=MUTED).pack(
            anchor="w", padx=24, pady=(20, 4))
        drow = ctk.CTkFrame(win, fg_color="transparent")
        drow.pack(anchor="w", padx=20, pady=(2, 10))
        boxes: dict[str, tk.BooleanVar] = {}
        for d in ("web", "crypto", "misc", "forensics"):
            var = tk.BooleanVar(value=(d in ("web", "crypto", "forensics")))
            boxes[d] = var
            ctk.CTkCheckBox(drow, text=d, variable=var).pack(side="left", padx=6)

        ctk.CTkLabel(win, text="难度", font=self.bold_s, text_color=MUTED).pack(
            anchor="w", padx=24, pady=(6, 2))
        diff_seg = ctk.CTkSegmentedButton(win, values=["不限", "简单", "中等", "困难"])
        diff_seg.set("不限")
        diff_seg.pack(anchor="w", padx=24, pady=(2, 8))

        ctk.CTkLabel(win, text="每个方向最多解几道（0 = 不限）", font=self.bold_s,
                     text_color=MUTED).pack(anchor="w", padx=24, pady=(4, 2))
        max_entry = ctk.CTkEntry(win, width=120, font=self.mono)
        max_entry.insert(0, "3")
        max_entry.pack(anchor="w", padx=24, pady=(2, 8))

        hint = ctk.CTkLabel(win, text="", text_color="#ff6b6b", font=self.mono_s)
        hint.pack(anchor="w", padx=24, pady=(4, 0))

        def start() -> None:
            directions = [d for d, v in boxes.items() if v.get()]
            if not directions:
                hint.configure(text="至少勾选一个方向")
                return
            try:
                maxn = max(0, int(max_entry.get().strip() or "0"))
            except ValueError:
                maxn = 3
            diff = {"简单": "Easy", "中等": "Medium", "困难": "Hard"}.get(diff_seg.get())
            win.destroy()
            self._start_autosolve(directions, maxn, diff)

        ctk.CTkButton(win, text="开始 ▶", height=40, width=140, command=start).pack(
            anchor="w", padx=24, pady=(12, 20))

    def _start_autosolve(self, directions: list[str], maxn: int, diff: str | None) -> None:
        from core.platform import list_tokens
        tokens = list_tokens()
        if not tokens:
            messagebox.showwarning("开始打题", "没有 token（.env 里配 CTF2_AGENT_TOKEN_0/1/2）",
                                   parent=self.root)
            return
        self._auto_slots = []
        persisted_failed = self.manager.failed_ids()
        for i, direction in enumerate(directions):
            if i >= len(tokens):
                break
            self._auto_slots.append({
                "running": True, "direction": direction, "token": tokens[i],
                "max": maxn, "difficulty": diff, "done": 0,
                "failed": set(persisted_failed),
                "current": None, "current_meta": None, "phase": "idle", "queue": queue.Queue(),
            })
        self.btn_auto.configure(text="⏹ 停止打题")
        self._table_sig = None
        self._render_table()

    def _autosolve_step(self) -> None:
        """Advance every auto-solve slot (called from _poll)."""
        for slot in list(self._auto_slots):
            if not slot["running"]:
                continue
            self._step_slot(slot)
        if self._auto_slots and not any(s["running"] for s in self._auto_slots):
            self.btn_auto.configure(text="▶ 开始打题")

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
                self._table_sig = None
            elif kind == "spec":
                spec, meta = result[1]
                # remember which platform challenge this session maps to, so the user can
                # retry this ONE challenge later (un-blacklist + re-fetch) without clearing all.
                spec = dict(spec)
                spec["platform_challenge_id"] = meta["challenge_id"]
                spec["platform_ground_id"] = meta["ground_id"]
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
                self._table_sig = None
            else:
                # "error" = this ONE challenge failed to prepare (its env didn't start,
                # download failed, …) → skip it and keep going. "stop" = genuinely no more.
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
                    slot["phase"] = "idle"  # fetch the next challenge instead of stopping
                else:
                    self._stop_slot(slot, msg)
                self._table_sig = None
        elif slot["phase"] == "solving":
            session = slot["current"]
            if session is not None and session.state["done"]:
                self._submit_slot(slot)

    def _autosolve_worker(self, slot: dict) -> None:
        try:
            from core.autosolve import PLATFORM_CATEGORY, prepare_challenge
            from core.platform import PlatformClient
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
                # show a placeholder session right away while we download/start the env
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
        from core.platform import PlatformClient, PlatformError
        session = slot["current"]
        meta = slot["current_meta"]
        slot["current"] = None
        slot["current_meta"] = None
        client = PlatformClient(token=slot["token"])
        try:
            flag = session.state.get("flag") if session else None
            solved = False  # True only if the platform actually flipped is_solved
            try:
                if flag:
                    try:
                        client.submit_flag(meta["ground_id"], meta["challenge_id"], flag)
                    except PlatformError as e:
                        print(f"[autosolve:{slot['direction']}] submit rejected: {e.code}")
                    else:
                        # The API may accept a wrong flag silently; confirm the challenge
                        # actually flipped to is_solved before counting it as a solve.
                        solved = self._challenge_solved(client, meta)
                client.log_note(meta["challenge_id"], "result",
                                (f"solved: {flag}" if flag else "no flag found")[:2000])
            except Exception as e:
                print(f"[autosolve:{slot['direction']}] submit/note error: {e}")
            # Always free the environment slot, even if submit/note failed — a leaked
            # target blocks every later challenge for this agent.
            try:
                client.delete_environment(meta["ground_id"], meta["challenge_id"])
            except Exception as e:
                print(f"[autosolve:{slot['direction']}] delete env error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass
        if flag and solved:
            slot["done"] += 1
        else:
            cid = str(meta["challenge_id"])
            slot.setdefault("failed", set()).add(cid)
            self.manager.add_failed(cid, slot["direction"])
        if slot["max"] and slot["done"] >= slot["max"]:
            self._stop_slot(slot, f"{slot['direction']} 已解出上限（{slot['done']} 道）")
        else:
            slot["phase"] = "idle"
        self._table_sig = None

    def _challenge_solved(self, client, meta: dict) -> bool:
        """Re-query the challenge to confirm the platform actually marked it solved."""
        try:
            ch = client.get_challenge(meta["ground_id"], meta["challenge_id"])
            return bool(ch.get("is_solved"))
        except Exception:
            return False

    def _stop_slot(self, slot: dict, msg: str) -> None:
        slot["running"] = False
        slot["phase"] = "idle"
        slot["current"] = None
        slot["current_meta"] = None
        print(f"[autosolve:{slot['direction']}] {msg}")

    # =====================================================================
    #  page: 手动解题
    # =====================================================================
    def _build_manual_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.main, fg_color="transparent")
        card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        card.pack(padx=48, pady=30, fill="x", anchor="n")
        hf = self.bold_s

        ctk.CTkLabel(card, text="手动解题", font=self.bold).pack(anchor="w", padx=26, pady=(22, 12))
        ctk.CTkLabel(card, text="方向", text_color=MUTED, font=hf).pack(anchor="w", padx=26)
        self.manual_dir = ctk.CTkSegmentedButton(card, values=["web", "crypto", "forensics"],
                                                 command=lambda _v: self._on_manual_dir())
        self.manual_dir.set("web")
        self.manual_dir.pack(anchor="w", padx=26, pady=(4, 0))

        # URL section (web only)
        self.manual_url_section = ctk.CTkFrame(card, fg_color="transparent")
        self.manual_url_section.pack(anchor="w", padx=26, fill="x")
        ctk.CTkLabel(self.manual_url_section, text="TARGET URLs（每行一个，web 必填）",
                     text_color=MUTED, font=hf).pack(anchor="w", pady=(12, 2))
        self.manual_urls = ctk.CTkTextbox(self.manual_url_section, height=52, font=self.mono)
        self.manual_urls.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(card, text="题目描述 / 提示", text_color=MUTED, font=hf).pack(
            anchor="w", padx=26, pady=(10, 2))
        self.manual_desc = ctk.CTkEntry(card, width=520, font=self.mono)
        self.manual_desc.pack(anchor="w", padx=26)

        ctk.CTkLabel(card, text="附件", text_color=MUTED, font=hf).pack(
            anchor="w", padx=26, pady=(10, 2))
        self.manual_attach_box = ctk.CTkFrame(card, fg_color="transparent")
        self.manual_attach_box.pack(anchor="w", padx=26, fill="x")
        ctk.CTkButton(card, text="＋ 添加文件", width=110, height=28,
                      command=self._add_manual_attachment).pack(anchor="w", padx=26, pady=(4, 0))

        opt = ctk.CTkFrame(card, fg_color="transparent")
        opt.pack(anchor="w", padx=26, pady=(10, 0))
        ctk.CTkLabel(opt, text="max turns", text_color=MUTED, font=hf).pack(anchor="w")
        self.manual_turns = ctk.CTkEntry(opt, width=120, font=self.mono)
        self.manual_turns.insert(0, "100")
        self.manual_turns.pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(opt, text="flag prefix", text_color=MUTED, font=hf).pack(anchor="w", pady=(8, 0))
        self.manual_prefix = ctk.CTkEntry(opt, width=120, font=self.mono)
        self.manual_prefix.insert(0, "flag")
        self.manual_prefix.pack(anchor="w", pady=(4, 0))

        self.manual_hint = ctk.CTkLabel(card, text="", text_color="#ff6b6b", font=self.mono_s)
        self.manual_hint.pack(anchor="w", padx=26, pady=(10, 0))
        ctk.CTkButton(card, text="开始 ▶", height=40, width=150,
                      command=self._start_manual).pack(anchor="w", padx=26, pady=(8, 22))
        return page

    def _on_manual_dir(self) -> None:
        if self.manual_dir.get() == "web":
            self.manual_url_section.pack(anchor="w", padx=26, fill="x")
        else:
            self.manual_url_section.pack_forget()

    def _add_manual_attachment(self) -> None:
        paths = filedialog.askopenfilenames(parent=self.root, title="选择附件")
        for p in paths:
            if p and p not in self._manual_attachments and Path(p).is_file():
                self._manual_attachments.append(p)
        self._render_manual_attachments()

    def _render_manual_attachments(self) -> None:
        for child in self.manual_attach_box.winfo_children():
            child.destroy()
        for p in self._manual_attachments:
            row = ctk.CTkFrame(self.manual_attach_box, fg_color="transparent")
            row.pack(anchor="w", pady=2)
            ctk.CTkLabel(row, text=Path(p).name, font=self.mono_s, text_color=FG).pack(side="left")
            ctk.CTkButton(row, text="−", width=28, height=24,
                          command=lambda p=p: self._remove_manual_attachment(p)).pack(
                side="left", padx=(4, 0))

    def _remove_manual_attachment(self, path: str) -> None:
        if path in self._manual_attachments:
            self._manual_attachments.remove(path)
        self._render_manual_attachments()

    def _start_manual(self) -> None:
        direction = self.manual_dir.get()
        urls = [u.strip() for u in (self.manual_urls.get("1.0", "end").strip().splitlines()) if u.strip()]
        if direction == "web" and not urls:
            self.manual_hint.configure(text="web 方向至少填一个 URL")
            return
        for u in urls:
            if not (u.startswith("http://") or u.startswith("https://")):
                self.manual_hint.configure(text="URL 必须以 http:// 或 https:// 开头")
                return
        if direction != "web":
            urls = []
        try:
            max_turns = max(1, int(self.manual_turns.get().strip() or "100"))
        except ValueError:
            max_turns = 100
        spec = {
            "kind": "custom",
            "category": direction,
            "urls": urls,
            "description": self.manual_desc.get().strip(),
            "flag_prefix": self.manual_prefix.get().strip() or "flag",
            "attachments": list(self._manual_attachments),
            "max_turns": max_turns,
        }
        title = urls[0].split("/", 2)[-1] if urls else direction
        self.manager.new_session(spec, title, direction)
        self.manual_hint.configure(text="")
        self._show_page("ctf")

    # =====================================================================
    #  page: 配置管理
    # =====================================================================
    def _build_config_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.main, fg_color="transparent")
        card = ctk.CTkFrame(page, fg_color=CARD_BG, corner_radius=14)
        card.pack(padx=48, pady=30, fill="x", anchor="n")
        ctk.CTkLabel(card, text="配置管理", font=self.bold).pack(anchor="w", padx=26, pady=(22, 6))
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(anchor="w", padx=26, pady=(0, 8))
        ctk.CTkButton(btn_row, text="🔄 刷新", width=100, height=30, font=self.mono_s,
                      command=self._refresh_config).pack(side="left")
        ctk.CTkButton(btn_row, text="清空失败黑名单", width=140, height=30, font=self.mono_s,
                      fg_color=DANGER, hover_color=DANGER_HOVER,
                      command=self._clear_failed).pack(side="left", padx=(8, 0))
        self.config_box = ctk.CTkTextbox(card, font=self.mono_s, height=360, wrap="word")
        self.config_box.pack(fill="both", expand=True, padx=26, pady=(4, 8))
        self.config_box.configure(state="disabled")
        ctk.CTkLabel(card, text="配置通过 .env 修改（DEEPSEEK_API_KEY / CTF_MODEL / CTF_API_BASE / "
                               "CTF2_AGENT_TOKEN_0..N）。修改后重启 GUI 生效。",
                     text_color=MUTED, font=self.mono_s, anchor="w").pack(
            anchor="w", padx=26, pady=(0, 22))
        self._refresh_config()
        return page

    def _clear_failed(self) -> None:
        n = len(self.manager.failed_ids())
        if n and not messagebox.askyesno("清空失败黑名单",
                                         f"清空 {n} 道已记录的失败题目？下次打题会重新尝试它们。",
                                         parent=self.root):
            return
        self.manager.clear_failed()
        self._refresh_config()

    def _refresh_config(self) -> None:
        import core.config as cfg
        from core.platform import list_tokens
        key = "已设置" if cfg.API_KEY else "未设置"
        if cfg.API_KEY:
            key += f"（{'*' * 6}{cfg.API_KEY[-4:]}）"
        text = (
            f"模型:        {cfg.DEFAULT_MODEL}\n"
            f"API Base:    {cfg.API_BASE}\n"
            f"API Key:     {key}\n"
            f"API 超时:    {cfg.API_TIMEOUT:.0f}s\n"
            f"Agent token: {len(list_tokens())} 个\n"
            f"失败黑名单:  {len(self.manager.failed_ids())} 道\n"
        )
        self.config_box.configure(state="normal")
        self.config_box.delete("1.0", "end")
        self.config_box.insert("end", text)
        self.config_box.configure(state="disabled")

    # =====================================================================
    #  poll + refresh
    # =====================================================================
    def _poll(self) -> None:
        try:
            self.manager.drain_all()
            self._drain_retry_queue()
            self._autosolve_step()
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self.root.after(self.poll_ms, self._poll)

    def _refresh_table_loop(self) -> None:
        # Rebuild the table only when the (id, status) signature actually changed.
        sig = tuple((s.id, s.state["status"]) for s in self.manager.sessions)
        if sig != self._table_sig:
            self._table_sig = sig
            self._render_table()
        self.root.after(1000, self._refresh_table_loop)

    def _install_signal_handlers(self) -> None:
        def _shutdown(signum: int, frame: Any) -> None:
            try:
                self.manager.stop_all()
            finally:
                try:
                    self.root.destroy()
                except Exception:
                    pass
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, _shutdown)
            except (ValueError, OSError):
                pass

    def run(self) -> None:
        self.root.mainloop()
