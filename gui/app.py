"""CustomTkinter supervision console (view). Chat-app layout over a Manager:

- left rail: folders and, under them, one button per session (a solve in its own
  subprocess), with a live spinner while running; click to switch the center conversation;
- center: the active session as real chat bubbles — agent, tool blocks, your guidance;
- right: a rich state panel (animated status, timer, tool/path findings, flag) with a stop
  button, a rename action, and copy buttons;
- bottom: guidance input for the active session.

Only rendering lives here; all agent logic is in the Session subprocess.
"""

import queue
import signal
import threading
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog
from urllib.parse import urlparse

import customtkinter as ctk

from typing import Any

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from .manager import Manager, Session

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

FG = "#d6dae3"
MUTED = "#7f8a9b"
AGENT_BG = "#1f2a3d"
GUIDE_BG = "#3a3017"
GUIDE_FG = "#ffdca8"
TOOL_BG = "#171c27"
RESULT_BG = "#14181f"
TOOL_FG = "#c3a0ff"
RAIL_SEL = "#243043"
FOLDER_FG = "#9aa5b5"
STATUS_COLORS = {
    "running": "#ffd166", "solved": "#79d98a", "failed": "#ff6b6b",
    "error": "#ff6b6b", "idle": "#8b94a7", "cancelled": "#c98a3d",
    "preparing": "#8b94a7",
}
STATUS_GLYPH = {"solved": "✓", "failed": "✗", "error": "⚠", "idle": "○",
                "cancelled": "■", "preparing": "…"}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
MAX_OUT = 1400
MAX_BUBBLE = 2000
MAX_RENDER_EVENTS = 20
WRAP = 560


class ConsoleApp:
    def __init__(self, manager: Manager, poll_ms: int = 150) -> None:
        self.manager = manager
        self.poll_ms = poll_ms
        self.frame = 0
        self._rendered: dict[int, int] = {}
        self._rows: dict[int, ctk.CTkButton] = {}
        self._inherit: dict[str, Any] | None = None
        self._auto_slots: list[dict[str, Any]] = []  # one slot per (direction, token)

        self.root = ctk.CTk()
        self.root.title("odele-ctf · supervision console")
        self.root.geometry("1220x760")
        self.mono = ctk.CTkFont(family="Menlo", size=12)
        self.mono_s = ctk.CTkFont(family="Menlo", size=11)
        self.bold = ctk.CTkFont(family="Menlo", size=15, weight="bold")

        self._build()
        self._render_rail()  # show sessions restored from disk
        self.root.bind("<Command-c>", self._copy_flag)
        self.root.bind("<Control-c>", self._copy_flag)
        self.root.after(poll_ms, self._poll)
        self.root.after(90, self._animate)
        self._install_signal_handlers()

    def _install_signal_handlers(self) -> None:
        """Terminate worker subprocesses on SIGINT/SIGTERM so a hard kill doesn't leak
        orphaned workers that keep burning API calls."""
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
                pass  # not the main thread, or unsupported

    # --- layout ------------------------------------------------------------
    def _build(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=0)  # rail: fixed 230px
        self.root.grid_columnconfigure(1, weight=1)  # main area fills
        self._build_rail()
        self._build_main()

    def _build_main(self) -> None:
        self.main = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#0f1218")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        self.center_head = ctk.CTkLabel(self.main, text="", text_color=FG, font=self.bold, anchor="w")
        self.center_head.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))

        # the session view (status + tabs + flag + suggestion), shown when a session is active
        self.session_view = self._build_session_view(self.main)
        self.session_view.grid(row=1, column=0, sticky="nsew")
        self.session_view.grid_remove()

        # the forms, shown when no session is active
        self.setup = self._build_setup(self.main)
        self.setup.grid(row=1, column=0, sticky="nsew")
        self.autosolve = self._build_autosolve(self.main)
        self.autosolve.grid(row=1, column=0, sticky="nsew")
        self.autosolve.grid_remove()

        self._show_setup()

    def _build_session_view(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        view = ctk.CTkFrame(parent, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        # status row
        top = ctk.CTkFrame(view, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(2, 2))
        self.big_status = ctk.CTkLabel(top, text="○ idle", font=self.bold, text_color=MUTED)
        self.big_status.pack(side="left", anchor="w")
        self.lbl_timer = ctk.CTkLabel(top, text="⏱ 0s", text_color=MUTED, font=self.mono)
        self.lbl_timer.pack(side="left", padx=(12, 0))
        self.lbl_counts = ctk.CTkLabel(top, text="replies 0 · tool calls 0", font=self.mono)
        self.lbl_counts.pack(side="left", padx=(12, 0))
        self.lbl_tools = ctk.CTkLabel(top, text="", text_color=MUTED, font=self.mono_s)
        self.lbl_tools.pack(side="left", padx=(12, 0))
        self.btn_stop = ctk.CTkButton(top, text="■ Stop", width=72, height=30,
                                      fg_color="#5a2b2b", hover_color="#703636",
                                      command=self._stop_active)
        self.btn_stop.pack(side="right")
        self.btn_delete = ctk.CTkButton(top, text="🗑", width=40, height=30,
                                        fg_color="#5a2b2b", hover_color="#703636",
                                        state="disabled", command=self._delete_active)
        self.btn_delete.pack(side="right", padx=(0, 4))

        # tab bar: 对话 / Findings / Thinking / 题解
        tabbar = ctk.CTkFrame(view, fg_color="transparent")
        tabbar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.btn_tab_chat = ctk.CTkButton(tabbar, text="对话", width=64, height=26,
                                          command=lambda: self._switch_tab("chat"))
        self.btn_tab_chat.pack(side="left", padx=(0, 4))
        self.btn_tab_findings = ctk.CTkButton(tabbar, text="Findings", width=72, height=26,
                                              command=lambda: self._switch_tab("findings"))
        self.btn_tab_findings.pack(side="left", padx=(0, 4))
        self.btn_tab_think = ctk.CTkButton(tabbar, text="Thinking", width=72, height=26,
                                           command=lambda: self._switch_tab("thinking"))
        self.btn_tab_think.pack(side="left", padx=(0, 4))
        self.btn_tab_writeup = ctk.CTkButton(tabbar, text="题解", width=56, height=26,
                                             command=lambda: self._switch_tab("writeup"))
        self.btn_tab_writeup.pack(side="left")

        # tab content
        self.tab_content = ctk.CTkFrame(view, fg_color="transparent")
        self.tab_content.grid(row=2, column=0, sticky="nsew", padx=16)

        self.frame_chat = ctk.CTkFrame(self.tab_content, fg_color="transparent")
        self.chat = ctk.CTkScrollableFrame(self.frame_chat, fg_color="transparent")
        self.chat.pack(fill="both", expand=True)

        self.frame_findings = ctk.CTkFrame(self.tab_content, fg_color="transparent")
        self.txt_findings = ctk.CTkTextbox(self.frame_findings, font=self.mono_s, wrap="word")
        self.txt_findings.pack(fill="both", expand=True)
        self._wheel_scroll(self.txt_findings)

        self.frame_think = ctk.CTkFrame(self.tab_content, fg_color="transparent")
        self.txt_think = ctk.CTkTextbox(self.frame_think, font=self.mono_s, wrap="word")
        self.txt_think.pack(fill="both", expand=True)
        self._wheel_scroll(self.txt_think)

        self.frame_writeup = ctk.CTkFrame(self.tab_content, fg_color="transparent")
        self.txt_writeup = ctk.CTkTextbox(self.frame_writeup, font=self.mono_s, wrap="word")
        self.txt_writeup.pack(fill="both", expand=True)
        self._wheel_scroll(self.txt_writeup)

        # flag row
        flag_row = ctk.CTkFrame(view, fg_color="transparent")
        flag_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 4))
        ctk.CTkLabel(flag_row, text="FLAG", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(side="left")
        self.lbl_flag = ctk.CTkLabel(flag_row, text="—", text_color="#79d98a", font=self.bold,
                                     anchor="w", justify="left", wraplength=400)
        self.lbl_flag.pack(side="left", padx=(8, 0), expand=True, fill="x")
        self._copy_btn(flag_row, lambda: self._copy(self._flag_now()))

        # suggestion bottom
        self.bottom = ctk.CTkFrame(view, corner_radius=0, fg_color="#141822")
        self.bottom.grid(row=4, column=0, sticky="ew")
        self.suggestion_entry = ctk.CTkEntry(
            self.bottom, placeholder_text="after it finishes: give a suggestion for the next attempt…",
            font=self.mono, height=38)
        self.suggestion_entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)
        self.suggestion_entry.bind("<Return>", lambda _e: self._continue_with_suggestion())
        ctk.CTkButton(self.bottom, text="Continue with suggestion",
                      command=self._continue_with_suggestion, width=190, height=38).pack(
            side="left", padx=(0, 12), pady=10)

        self._switch_tab("chat")
        return view

    def _build_rail(self) -> None:
        rail = ctk.CTkFrame(self.root, width=230, corner_radius=0)
        rail.grid(row=0, column=0, sticky="ns")
        rail.grid_propagate(False)
        ctk.CTkLabel(rail, text="SESSIONS", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 4))
        row = ctk.CTkFrame(rail, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 6))
        ctk.CTkButton(row, text="＋ Session", command=self._show_setup,
                      height=32, anchor="w").pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row, text="🗂", width=40, height=32, command=self._new_folder,
                      fg_color="#2a3648", hover_color="#35445a").pack(side="left")
        # auto-solve + search
        self.btn_auto = ctk.CTkButton(rail, text="🤖 CTF2 打题", command=self._toggle_autosolve,
                                      height=30, anchor="w", fg_color="#243043",
                                      hover_color="#35445a")
        self.btn_auto.pack(fill="x", padx=10, pady=(0, 6))
        self.search_entry = ctk.CTkEntry(rail, placeholder_text="搜索 session…", height=28,
                                         font=self.mono_s)
        self.search_entry.pack(fill="x", padx=10, pady=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._render_rail())
        self.rail_list = ctk.CTkScrollableFrame(rail, fg_color="transparent")
        self.rail_list.pack(fill="both", expand=True, padx=4)

    def _build_setup(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        card = ctk.CTkFrame(wrap, fg_color="#141a24", corner_radius=14)
        card.pack(padx=48, pady=28, fill="x", anchor="n")
        hf = ctk.CTkFont(family="Menlo", size=11, weight="bold")
        ctk.CTkLabel(card, text="Start a new session", font=self.bold).pack(
            anchor="w", padx=26, pady=(22, 12))

        # --- name / folder / max turns at the top --------------------------
        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(anchor="w", padx=26)
        ctk.CTkLabel(opt_row, text="name", text_color=MUTED, font=hf).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(opt_row, placeholder_text="(auto from target)",
                                       width=260, font=self.mono)
        self.name_entry.pack(anchor="w", pady=(4, 6))
        ctk.CTkLabel(opt_row, text="folder", text_color=MUTED, font=hf).pack(anchor="w")
        self.folder_menu = ctk.CTkOptionMenu(opt_row, values=["(none)"], width=260,
                                             command=lambda _v: None)
        self.folder_menu.pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(opt_row, text="max turns", text_color=MUTED, font=hf).pack(anchor="w", pady=(8, 0))
        self.turns_entry = ctk.CTkEntry(opt_row, width=120, font=self.mono)
        self.turns_entry.insert(0, "100")
        self.turns_entry.pack(anchor="w", pady=(4, 0))

        # --- direction (picks the toolset) --------------------------------
        ctk.CTkLabel(card, text="direction", text_color=MUTED, font=hf).pack(
            anchor="w", padx=26, pady=(10, 2))
        self.dir_seg = ctk.CTkSegmentedButton(card, values=["web", "crypto", "forensics"],
                                              command=lambda _v: self._on_direction_changed())
        self.dir_seg.set("web")
        self.dir_seg.pack(anchor="w", padx=26, pady=(0, 4))

        # --- description / flag prefix ------------------------------------
        self.desc_entry = ctk.CTkEntry(card, placeholder_text="description / hint (optional)",
                                       width=440, font=self.mono)
        self.desc_entry.pack(anchor="w", padx=26, pady=(14, 4))
        self.flag_entry = ctk.CTkEntry(card, placeholder_text="flag prefix (optional, default 'flag')",
                                       width=280, font=self.mono)
        self.flag_entry.pack(anchor="w", padx=26, pady=4)

        # --- target URLs (web only) --------------------------------------
        self.url_section = ctk.CTkFrame(card, fg_color="transparent")
        self.url_section.pack(anchor="w", padx=26, fill="x")
        ctk.CTkLabel(self.url_section, text="TARGET URLs", text_color=MUTED, font=hf).pack(
            anchor="w", pady=(10, 2))
        self.urls_box = ctk.CTkFrame(self.url_section, fg_color="transparent", height=0)
        self.urls_box.pack(anchor="w", fill="x")
        self.url_entries: list[ctk.CTkEntry] = []
        self._add_url_row("")
        ctk.CTkButton(self.url_section, text="＋ Add URL", width=110, height=26,
                      command=lambda: self._add_url_row("")).pack(anchor="w", pady=(2, 0))

        # --- attachments --------------------------------------------------
        ctk.CTkLabel(card, text="ATTACHMENTS", text_color=MUTED, font=hf).pack(
            anchor="w", padx=26, pady=(10, 2))
        self.attach_box = ctk.CTkFrame(card, fg_color="transparent", height=0)
        self.attach_box.pack(anchor="w", padx=26, fill="x")
        self._attachment_paths: list[str] = []
        ctk.CTkButton(card, text="＋ Add file", width=110, height=26,
                      command=self._add_attachment).pack(anchor="w", padx=26, pady=(2, 8))

        self.setup_hint = ctk.CTkLabel(card, text="", text_color="#ff6b6b", font=self.mono_s)
        self.setup_hint.pack(anchor="w", padx=26, pady=(10, 0))
        ctk.CTkButton(card, text="Start  ▶", command=self._start_from_setup,
                      height=42, width=150).pack(anchor="w", padx=26, pady=(8, 22))
        return wrap

    def _build_autosolve(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        card = ctk.CTkFrame(wrap, fg_color="#141a24", corner_radius=14)
        card.pack(padx=48, pady=28, fill="x", anchor="n")
        hf = ctk.CTkFont(family="Menlo", size=11, weight="bold")
        ctk.CTkLabel(card, text="CTF2 自动打题", font=self.bold).pack(anchor="w", padx=26, pady=(22, 12))

        ctk.CTkLabel(card, text="DIRECTION（多选）", text_color=MUTED, font=hf).pack(anchor="w", padx=26)
        drow = ctk.CTkFrame(card, fg_color="transparent")
        drow.pack(anchor="w", padx=22, pady=(6, 14))
        self.auto_dir_boxes: dict[str, tk.BooleanVar] = {}
        for d in ["web", "crypto", "misc", "forensics", "pwn", "reverse", "ai"]:
            var = tk.BooleanVar(value=(d in ("web", "crypto", "forensics")))
            self.auto_dir_boxes[d] = var
            ctk.CTkCheckBox(drow, text=d, variable=var).pack(side="left", padx=6, pady=3)

        ctk.CTkLabel(card, text="DIFFICULTY", text_color=MUTED, font=hf).pack(anchor="w", padx=26)
        self.auto_diff_seg = ctk.CTkSegmentedButton(card, values=["不限", "简单", "中等", "困难"])
        self.auto_diff_seg.set("不限")
        self.auto_diff_seg.pack(anchor="w", padx=26, pady=(4, 14))

        ctk.CTkLabel(card, text="每个方向最多解几道（0 = 不限）", text_color=MUTED, font=hf).pack(anchor="w", padx=26)
        self.auto_max_entry = ctk.CTkEntry(card, width=120, font=self.mono)
        self.auto_max_entry.insert(0, "3")
        self.auto_max_entry.pack(anchor="w", padx=26, pady=(4, 14))

        self.auto_hint = ctk.CTkLabel(card, text="", text_color="#ff6b6b", font=self.mono_s)
        self.auto_hint.pack(anchor="w", padx=26)
        brow = ctk.CTkFrame(card, fg_color="transparent")
        brow.pack(anchor="w", padx=26, pady=(10, 22))
        ctk.CTkButton(brow, text="开始 ▶", command=self._start_autosolve, height=38, width=140).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(brow, text="返回", command=self._show_setup, height=38, width=100,
                      fg_color="#2a3648", hover_color="#35445a").pack(side="left")
        return wrap

    def _show_autosolve(self) -> None:
        self.manager.active = None
        self.center_head.configure(text="CTF2 自动打题")
        self.session_view.grid_remove()
        self.setup.grid_remove()
        self.autosolve.grid()
        self.auto_hint.configure(text="")

    def _start_autosolve(self) -> None:
        directions = [d for d, var in self.auto_dir_boxes.items() if var.get()]
        if not directions:
            self.auto_hint.configure(text="至少勾选一个方向")
            return
        try:
            maxn = max(0, int(self.auto_max_entry.get().strip() or "0"))
        except ValueError:
            maxn = 3
        diff = {"简单": "Easy", "中等": "Medium", "困难": "Hard"}.get(self.auto_diff_seg.get())
        from core.platform import list_tokens
        tokens = list_tokens()
        if not tokens:
            self.auto_hint.configure(text="没有 token（.env 里配 CTF2_AGENT_TOKEN_0/1/2）")
            return
        self._auto_slots = []
        for i, direction in enumerate(directions):
            if i >= len(tokens):
                break
            folder = f"ctf2_{direction}"
            if folder not in self.manager.folders:
                self.manager.new_folder(folder)
            self._auto_slots.append({
                "running": True, "direction": direction, "token": tokens[i],
                "max": maxn, "difficulty": diff, "done": 0, "current": None,
                "current_meta": None, "phase": "idle", "queue": queue.Queue(),
            })
        self.btn_auto.configure(text="⏹ 停止打题")
        self._render_rail()
        # show the (empty) session view; sessions auto-select as they spawn
        self.autosolve.grid_remove()
        self.session_view.grid()
        self._switch_tab("chat")

    def _on_direction_changed(self) -> None:
        """Show the URL section only for web targets; crypto/forensics don't need a URL."""
        if self.dir_seg.get() == "web":
            self.url_section.pack(anchor="w", padx=26, fill="x")
        else:
            self.url_section.pack_forget()

    def _add_url_row(self, value: str = "") -> None:
        row = ctk.CTkFrame(self.urls_box, fg_color="transparent")
        row.pack(anchor="w", pady=2)
        entry = ctk.CTkEntry(row, placeholder_text="https://target.ctf/…", width=440, font=self.mono)
        entry.pack(side="left")
        if value:
            entry.insert(0, value)
        ctk.CTkButton(row, text="−", width=28, height=28, fg_color="#2a3648",
                      hover_color="#35445a",
                      command=lambda: self._remove_url_row(row, entry)).pack(side="left", padx=(4, 0))
        self.url_entries.append(entry)

    def _remove_url_row(self, row: ctk.CTkFrame, entry: ctk.CTkEntry) -> None:
        row.destroy()
        if entry in self.url_entries:
            self.url_entries.remove(entry)
        if not self.url_entries:
            self._add_url_row("")

    def _collect_urls(self) -> list[str]:
        return [e.get().strip() for e in self.url_entries if e.get().strip()]

    def _add_attachment(self) -> None:
        paths = filedialog.askopenfilenames(parent=self.root, title="Select attachment file(s)")
        for p in paths:
            if p and p not in self._attachment_paths and Path(p).is_file():
                self._attachment_paths.append(p)
        self._render_attachments()

    def _remove_attachment(self, path: str) -> None:
        if path in self._attachment_paths:
            self._attachment_paths.remove(path)
        self._render_attachments()

    def _render_attachments(self) -> None:
        for child in self.attach_box.winfo_children():
            child.destroy()
        for p in self._attachment_paths:
            row = ctk.CTkFrame(self.attach_box, fg_color="transparent")
            row.pack(anchor="w", pady=2)
            ctk.CTkLabel(row, text=Path(p).name, font=self.mono_s, anchor="w",
                         text_color=TOOL_FG).pack(side="left")
            ctk.CTkButton(row, text="−", width=28, height=28, fg_color="#2a3648",
                          hover_color="#35445a",
                          command=lambda path=p: self._remove_attachment(path)).pack(
                side="left", padx=(4, 0))

    def _refresh_folder_options(self) -> None:
        self.folder_menu.configure(values=["(none)"] + self.manager.folders)
        if self.folder_menu.get() not in ["(none)"] + self.manager.folders:
            self.folder_menu.set("(none)")

    def _show_setup(self) -> None:
        self.manager.active = None
        for btn in self._rows.values():
            btn.configure(fg_color="transparent")
        if hasattr(self, "btn_delete"):
            self.btn_delete.configure(state="disabled")
        self.center_head.configure(text="New session")
        self.session_view.grid_remove()
        self.autosolve.grid_remove()
        self.setup.grid()
        self._reset_setup()
        self._refresh_folder_options()

    def _reset_setup(self) -> None:
        """Clear every setup field back to defaults so a fresh '＋ Session' starts blank."""
        self.name_entry.delete(0, "end")
        self.turns_entry.delete(0, "end")
        self.turns_entry.insert(0, "100")
        self.folder_menu.set("(none)")
        self.dir_seg.set("web")
        self._on_direction_changed()
        self.desc_entry.delete(0, "end")
        self.flag_entry.delete(0, "end")
        for child in self.urls_box.winfo_children():
            child.destroy()
        self.url_entries.clear()
        self._add_url_row("")
        self._attachment_paths.clear()
        self._render_attachments()
        self.setup_hint.configure(text="")

    def _start_from_setup(self) -> None:
        direction = self.dir_seg.get()
        urls = self._collect_urls()
        if direction == "web":
            if not urls:
                self.setup_hint.configure(text="enter at least one target URL (http:// or https://)")
                return
            for u in urls:
                if not (u.startswith("http://") or u.startswith("https://")):
                    self.setup_hint.configure(text="target URLs must start with http:// or https://")
                    return
            title = urlparse(urls[0]).netloc or urls[0][:28]
        else:
            urls = []  # crypto/forensics are local/offline — no URL needed
            title = direction
        spec = {"kind": "custom", "category": direction, "urls": urls,
                "description": self.desc_entry.get().strip(),
                "flag_prefix": self.flag_entry.get().strip() or "flag",
                "attachments": list(self._attachment_paths)}
        category = direction
        custom_name = self.name_entry.get().strip()
        if custom_name:
            title = custom_name
        folder = self.folder_menu.get()
        folder = None if folder == "(none)" else folder
        try:
            spec["max_turns"] = max(1, int(self.turns_entry.get().strip() or "100"))
        except ValueError:
            spec["max_turns"] = 100
        inherit = None
        if self._inherit:
            spec["context"] = self._inherit["context"]
            inherit = self._inherit.get("source")
            self._inherit = None
        self.setup_hint.configure(text="")
        self.setup.grid_remove()
        self.add_session(self.manager.new_session(spec, title, category, folder=folder,
                                                  inherit=inherit))

    def _flag_now(self) -> str:
        a = self.manager.active
        return (a.state.get("flag") or "") if a else ""

    def _header(self, parent: ctk.CTkFrame, text: str, copy_cmd) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16)
        ctk.CTkLabel(row, text=text, text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(side="left")
        self._copy_btn(row, copy_cmd)

    def _copy_btn(self, parent: ctk.CTkFrame, cmd) -> None:
        ctk.CTkButton(parent, text="⧉", width=28, height=24, fg_color="#232b3a",
                      hover_color="#35445a", font=self.mono_s, command=cmd).pack(side="right")

    def _wheel_scroll(self, box: ctk.CTkTextbox) -> None:
        """customtkinter's scrollbar only binds Linux Button-4/5, not the macOS/Windows
        <MouseWheel>, so bind the wheel here to scroll the textbox."""
        text = box._textbox

        def handler(event: Any) -> str:
            delta = getattr(event, "delta", 0)
            if delta:
                text.yview_scroll(-1 if delta > 0 else 1, "units")
            elif getattr(event, "num", 0) == 4:
                text.yview_scroll(-1, "units")
            elif getattr(event, "num", 0) == 5:
                text.yview_scroll(1, "units")
            return "break"

        box.bind("<MouseWheel>", handler)
        box.bind("<Button-4>", handler)
        box.bind("<Button-5>", handler)

    def _switch_tab(self, name: str) -> None:
        self._active_tab = name
        for frame in (self.frame_chat, self.frame_findings, self.frame_think, self.frame_writeup):
            frame.pack_forget()
        for btn in (self.btn_tab_chat, self.btn_tab_findings, self.btn_tab_think, self.btn_tab_writeup):
            btn.configure(fg_color="transparent")
        if name == "findings":
            self.frame_findings.pack(fill="both", expand=True)
            self.btn_tab_findings.configure(fg_color="#2a3648")
        elif name == "thinking":
            self.frame_think.pack(fill="both", expand=True)
            self.btn_tab_think.configure(fg_color="#2a3648")
        elif name == "writeup":
            self.frame_writeup.pack(fill="both", expand=True)
            self.btn_tab_writeup.configure(fg_color="#2a3648")
        else:
            self.frame_chat.pack(fill="both", expand=True)
            self.btn_tab_chat.configure(fg_color="#2a3648")

    # --- sessions / folders ------------------------------------------------
    def _new_folder(self) -> None:
        name = simpledialog.askstring("New folder", "Folder name:", parent=self.root)
        if name and self.manager.new_folder(name):
            self._render_rail()

    # --- CTF2 auto-solve ---------------------------------------------------
    def _toggle_autosolve(self) -> None:
        if any(s["running"] for s in self._auto_slots):
            for s in self._auto_slots:
                s["running"] = False
            self._auto_slots = []
            self.btn_auto.configure(text="🤖 CTF2 打题")
            self._render_rail()
            return
        self._show_autosolve()

    def _autosolve_step(self) -> None:
        """Advance every auto-solve slot (called from _poll)."""
        for slot in list(self._auto_slots):
            if not slot["running"]:
                continue
            self._step_slot(slot)
        if self._auto_slots and not any(s["running"] for s in self._auto_slots):
            self.btn_auto.configure(text="🤖 CTF2 打题")

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
                    meta["name"], slot["direction"], folder=f"ctf2_{slot['direction']}")
                slot["pending"] = pending
                self.add_session(pending)
            elif kind == "spec":
                spec, meta = result[1]
                pending = slot.get("pending")
                if pending is not None:
                    self.manager.start_pending_session(pending, spec)
                    slot["pending"] = None
                    slot["current"] = pending
                    slot["current_meta"] = meta
                else:
                    session = self.manager.new_session(
                        spec, meta["name"], meta["category"], folder=f"ctf2_{slot['direction']}")
                    slot["current"] = session
                    slot["current_meta"] = meta
                    self.add_session(session)
                slot["phase"] = "solving"
            else:
                msg = result[1] if isinstance(result, tuple) else "打题结束"
                pending = slot.get("pending")
                if pending is not None:
                    pending.state["status"] = "error"
                    pending.state["done"] = True
                    slot["pending"] = None
                self._stop_slot(slot, msg)
        elif slot["phase"] == "solving":
            session = slot["current"]
            if session is not None and session.state["done"]:
                self._submit_slot(slot)

    def _autosolve_worker(self, slot: dict) -> None:
        try:
            from core.autosolve import prepare_challenge
            from core.platform import PlatformClient
            client = PlatformClient(token=slot["token"])
            try:
                nc = client.next_challenges(limit=10, difficulty=slot.get("difficulty"))
                items = nc.get("items") or []
                item = next((it for it in items
                             if str(it.get("category", "")).lower() == slot["direction"]), None)
                if item is None:
                    slot["queue"].put(("stop", f"{slot['direction']} 没有未解的题了"))
                    return
                # show a placeholder session right away while we download/start the env
                slot["queue"].put(("placeholder", {"name": item.get("name") or slot["direction"]}))
                try:
                    result = prepare_challenge(client, item)
                except Exception as e:
                    slot["queue"].put(("error", f"{item.get('name')}: {e}"))
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
            try:
                if flag:
                    try:
                        client.submit_flag(meta["ground_id"], meta["challenge_id"], flag)
                    except PlatformError as e:
                        print(f"[autosolve:{slot['direction']}] submit: {e.code}")
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
        slot["done"] += 1
        if slot["max"] and slot["done"] >= slot["max"]:
            self._stop_slot(slot, f"{slot['direction']} 已达上限（{slot['done']} 道）")
        else:
            slot["phase"] = "idle"

    def _stop_slot(self, slot: dict, msg: str) -> None:
        slot["running"] = False
        slot["phase"] = "idle"
        slot["current"] = None
        slot["current_meta"] = None
        print(f"[autosolve:{slot['direction']}] {msg}")

    def _render_rail(self) -> None:
        for child in self.rail_list.winfo_children():
            child.destroy()
        self._rows.clear()
        query = ""
        if hasattr(self, "search_entry"):
            query = (self.search_entry.get() or "").strip().lower()

        def matches(s: Session) -> bool:
            return (not query) or query in s.title.lower() or query in s.category.lower()

        for folder in self.manager.folders:
            self._folder_label(folder)
            for s in self.manager.sessions:
                if s.folder == folder and matches(s):
                    self._session_button(s, indent=True)
        for s in self.manager.sessions:
            if s.folder is None and matches(s):
                self._session_button(s, indent=False)

    def _folder_label(self, folder: str) -> None:
        lbl = ctk.CTkLabel(self.rail_list, text=f"▾  {folder}", text_color=FOLDER_FG,
                           anchor="w", font=ctk.CTkFont(family="Menlo", size=11, weight="bold"))
        lbl.pack(fill="x", padx=16, pady=(10, 2))

    def _session_button(self, session: Session, indent: bool) -> None:
        btn = ctk.CTkButton(self.rail_list, text=f"○  {session.title}", anchor="w",
                            fg_color="transparent", hover_color=RAIL_SEL, height=36,
                            command=lambda s=session: self.select(s))
        btn.pack(fill="x", pady=2, padx=(24 if indent else 8, 4))
        btn.bind("<Button-3>", lambda e, s=session: self._session_menu(e, s))
        self._rows[session.id] = btn

    def _session_menu(self, event: Any, session: Session) -> None:
        menu = tk.Menu(self.root, tearoff=0, bg="#141822", fg=FG,
                       activebackground=RAIL_SEL, activeforeground=FG)
        menu.add_command(label="Continue (inherit)",
                         command=lambda: self._select_then(session, self._continue_active))
        menu.add_command(label="Re-run (fresh)",
                         command=lambda: self._select_then(session, self._rerun_active))
        menu.add_command(label="Rename…",
                         command=lambda: self._select_then(session, self._rename_active))
        if session.is_running():
            menu.add_command(label="■ Stop",
                             command=lambda: self._select_then(session, self._stop_active))
        menu.add_separator()
        menu.add_command(label="🗑 Delete",
                         command=lambda: self._select_then(session, self._delete_active))
        menu.tk_popup(event.x_root, event.y_root)

    def _select_then(self, session: Session, fn) -> None:
        self.select(session)
        fn()

    def add_session(self, session: Session) -> None:
        self._render_rail()
        self._rendered.setdefault(session.id, 0)
        self.select(session)

    def select(self, session: Session) -> None:
        self.manager.active = session
        self.autosolve.grid_remove()
        self.setup.grid_remove()
        self.session_view.grid()
        self._switch_tab("chat")
        self.bottom.grid() if session.state["done"] else self.bottom.grid_remove()
        for sid, btn in self._rows.items():
            btn.configure(fg_color=RAIL_SEL if sid == session.id else "transparent")
        self.center_head.configure(text=f"{session.title}  ·  {session.category}", text_color=FG)
        for child in self.chat.winfo_children():
            child.destroy()
        transcript = session.transcript
        if len(transcript) > MAX_RENDER_EVENTS:
            hidden = len(transcript) - MAX_RENDER_EVENTS
            self._bubble("center", "#11151c", f"— {hidden} earlier events hidden —",
                         text_color=MUTED, font=self.mono_s)
            transcript = transcript[-MAX_RENDER_EVENTS:]
        self._rendered[session.id] = 0
        for ev in transcript:
            self._render(ev)
        self._rendered[session.id] = len(session.transcript)
        self._refresh_panel()

    # --- rendering (chat bubbles) -----------------------------------------
    def _bubble(self, anchor: str, bg: str, text: str, *, text_color: str = FG,
                font: Any = None, full: bool = False) -> None:
        holder = ctk.CTkFrame(self.chat, fg_color="transparent")
        holder.pack(fill="x", padx=6, pady=3)
        bubble = ctk.CTkFrame(holder, fg_color=bg, corner_radius=12)
        bubble.pack(fill="x" if full else None, anchor=anchor,
                    padx=(0, 70) if anchor == "w" and not full else ((70, 0) if anchor == "e" else 0))
        self._bubble_text(bubble, text, bg=bg, text_color=text_color, font=font or self.mono,
                          wrap_chars=80 if not full else 92, center=(anchor == "center"))
        self._scroll_bottom()

    def _bubble_text(self, parent: ctk.CTkFrame, text: str, *, bg: str, text_color: str,
                     font: Any, wrap_chars: int, center: bool = False) -> None:
        """A read-only, selectable text widget sized to fit the bubble (so text is copyable)."""
        fam = font.cget("family") if hasattr(font, "cget") else "Menlo"
        size = font.cget("size") if hasattr(font, "cget") else 12
        box = tk.Text(parent, wrap="word", width=wrap_chars, bd=0, relief="flat",
                      highlightthickness=0, bg=bg, fg=text_color, font=(fam, size),
                      cursor="xterm", padx=0, pady=0, insertwidth=0,
                      selectbackground="#3d4f73", selectforeground="#ffffff")
        box.insert("1.0", text)
        if center:
            box.tag_configure("center", justify="center")
            box.tag_add("center", "1.0", "end")
        box.configure(state="disabled")
        box.pack(anchor="center" if center else "w", padx=10, pady=6)
        # count display lines after packing so wrapping uses the real width (displaylines
        # returns the character count before the widget is mapped)
        box.update_idletasks()
        lines = box.count("1.0", "end", "displaylines")
        if isinstance(lines, tuple):
            lines = lines[0]
        box.configure(height=max(1, int(lines)))

    def _scroll_bottom(self) -> None:
        try:
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _clip(self, text: Any, n: int) -> str:
        text = str(text or "")
        if len(text) > n:
            return text[:n] + f"  …(+{len(text) - n})"
        return text

    def _render(self, ev: dict[str, Any]) -> None:
        if not isinstance(ev, dict):
            return
        kind = ev.get("type")
        if kind == "agent":
            self._bubble("w", AGENT_BG, f"🧠  {self._clip(ev.get('text', ''), MAX_BUBBLE)}")
        elif kind == "tool_call":
            args = self._clip(str(ev.get("args", "")), 800)
            self._bubble("w", TOOL_BG, f"⚙  {ev.get('name', '?')}  {args}",
                         text_color=TOOL_FG, font=self.mono_s, full=True)
        elif kind == "tool_result":
            out = self._clip(ev.get("output", ""), MAX_OUT)
            self._bubble("w", RESULT_BG, f"↳ {out}", text_color=MUTED, font=self.mono_s, full=True)
        elif kind == "guidance":
            self._bubble("e", GUIDE_BG, f"you ▸ {self._clip(ev.get('text', ''), 500)}",
                         text_color=GUIDE_FG)
        elif kind == "note":
            self._bubble("center", "#11151c", self._clip(ev.get("text", ""), 500),
                         text_color=MUTED, font=self.mono_s)
        elif kind == "writeup":
            self._bubble("center", "#11151c", "— 🧾 题解已生成 · 见右侧「题解」标签 —",
                         text_color=MUTED, font=self.mono_s)
        elif kind == "status":
            status = ev.get("status", "")
            if status in ("solved", "failed", "error", "cancelled"):
                extra = ev.get("flag") or ev.get("error") or ""
                self._bubble("center", "#11151c", f"— {status.upper()} {extra} —".strip(),
                             text_color=STATUS_COLORS.get(status, FG), font=self.mono, full=True)

    # --- behavior ----------------------------------------------------------
    def _continue_with_suggestion(self) -> None:
        session = self.manager.active
        suggestion = self.suggestion_entry.get().strip()
        if not session or not suggestion:
            return
        context = self._format_transcript(session)
        context += f"\n\nYour suggestion for the next attempt: {suggestion}"
        spec = dict(session.spec)
        spec["context"] = context
        spec["max_turns"] = session.spec.get("max_turns", 100)
        new_session = self.manager.new_session(spec, session.title, session.category,
                                               folder=session.folder, inherit=session)
        self.add_session(new_session)
        self.suggestion_entry.delete(0, "end")

    def _stop_active(self) -> None:
        if self.manager.active and self.manager.active.is_running():
            self.manager.stop(self.manager.active)
            self._bubble("center", "#11151c", "— CANCELLED —", text_color=STATUS_COLORS["cancelled"],
                         font=self.mono, full=True)
            self._refresh_panel()

    def _delete_active(self) -> None:
        session = self.manager.active
        if not session:
            return
        if not messagebox.askyesno(
            "Delete session",
            f"Delete “{session.title}”? This removes it from the list and from disk.",
            parent=self.root,
        ):
            return
        self.manager.delete(session)
        self._rendered.pop(session.id, None)
        self._render_rail()
        if self.manager.sessions:
            self.select(self.manager.sessions[0])
        else:
            self._show_setup()

    def _rename_active(self) -> None:
        if not self.manager.active:
            return
        name = simpledialog.askstring("Rename session", "Session name:",
                                      initialvalue=self.manager.active.title, parent=self.root)
        if name:
            self.manager.rename(self.manager.active, name)
            self.center_head.configure(text=f"{self.manager.active.title}  ·  {self.manager.active.category}")
            self._render_rail()

    def _format_transcript(self, session: Session) -> str:
        st = session.state
        lines = [
            "A previous session already worked on this target. Continue from where it left off, "
            "do NOT redo work already done, and pick up the most promising thread.\n"
        ]
        paths = st.get("paths") or []
        if paths:
            lines.append("[findings so far — build on these, do not rediscover them]")
            lines.append("\n".join(f"  - {p}" for p in paths))
            lines.append("")
        lines.append("[transcript]")
        for ev in session.transcript:
            kind = ev.get("type")
            if kind == "agent":
                lines.append(f"[agent] {ev.get('text', '')}")
            elif kind == "tool_call":
                lines.append(f"[tool {ev.get('name', '?')}] {ev.get('args', '')}")
            elif kind == "tool_result":
                out = str(ev.get("output", ""))
                if len(out) > 500:
                    out = out[:500] + " …"
                lines.append(f"[result] {out}")
            elif kind == "guidance":
                lines.append(f"[you] {ev.get('text', '')}")
            elif kind == "status":
                extra = ev.get("flag") or ev.get("error") or ""
                lines.append(f"[status] {ev.get('status', '')} {extra}".strip())
            # "note" events are GUI-only markers ("continued from …"); skip them.
        return "\n".join(lines)

    def _continue_active(self) -> None:
        session = self.manager.active
        if not session:
            return
        self._inherit = {
            "context": self._format_transcript(session),
            "spec": dict(session.spec),
            "source": session,
        }
        self._show_setup()
        self._prefill_setup(session.spec, session.title)
        if session.folder and session.folder in self.manager.folders:
            self.folder_menu.set(session.folder)

    def _rerun_active(self) -> None:
        session = self.manager.active
        if not session:
            return
        self._inherit = None  # fresh start, no inherited context
        self._show_setup()
        self._prefill_setup(session.spec, session.title)
        if session.folder and session.folder in self.manager.folders:
            self.folder_menu.set(session.folder)

    def _prefill_setup(self, spec: dict[str, Any], title: str) -> None:
        # Only custom targets are launched from the GUI now.
        direction = spec.get("category", "web")
        self.dir_seg.set(direction if direction in ("web", "crypto", "forensics") else "web")
        self._on_direction_changed()
        urls = spec.get("urls") or ([spec.get("url")] if spec.get("url") else [])
        for child in self.urls_box.winfo_children():
            child.destroy()
        self.url_entries.clear()
        for u in urls:
            self._add_url_row(u)
        if not urls:
            self._add_url_row("")
        self._attachment_paths = list(spec.get("attachments") or [])
        self._render_attachments()
        self.desc_entry.delete(0, "end"); self.desc_entry.insert(0, spec.get("description", ""))
        self.flag_entry.delete(0, "end"); self.flag_entry.insert(0, spec.get("flag_prefix", "flag"))
        self.turns_entry.delete(0, "end"); self.turns_entry.insert(0, str(spec.get("max_turns", 100)))
        self.name_entry.delete(0, "end"); self.name_entry.insert(0, title)

    def _copy(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _copy_flag(self, _event=None) -> None:
        w = self.root.focus_get()
        # customtkinter wraps its text/entry in an inner tkinter.Text/tkinter.Entry, so
        # focus_get() returns that inner widget — match it too, and leave copy to the
        # focused widget instead of clobbering the user's selection with the flag.
        if isinstance(w, (ctk.CTkTextbox, ctk.CTkEntry, tk.Text, tk.Entry)):
            return
        if self.manager.active and self.manager.active.state.get("flag"):
            self._copy(self.manager.active.state["flag"])

    def _findings_text(self) -> str:
        return self.txt_findings.get("1.0", "end").strip()

    def _thinking_text(self) -> str:
        return self.txt_think.get("1.0", "end").strip()

    def _set_text(self, box: ctk.CTkTextbox, text: str) -> None:
        if box.get("1.0", "end-1c") == text:
            return  # unchanged — rewriting here would clear the user's selection
        box.delete("1.0", "end")
        box.insert("end", text)

    def _poll(self) -> None:
        try:
            self.manager.drain_all()
            active = self.manager.active
            if active:
                start = self._rendered.get(active.id, 0)
                for ev in active.transcript[start:]:
                    self._render(ev)
                self._rendered[active.id] = len(active.transcript)
                self._refresh_panel()
            self._autosolve_step()
        except Exception:
            # A malformed event must never stop polling, or the console silently freezes.
            import traceback
            traceback.print_exc()
        finally:
            self.root.after(self.poll_ms, self._poll)

    def _refresh_panel(self) -> None:
        active = self.manager.active
        if not active:
            return
        st = active.state
        status = st["status"]
        spin = SPINNER[self.frame % len(SPINNER)] if active.is_running() else STATUS_GLYPH.get(status, "●")
        self.big_status.configure(text=f"{spin} {status}", text_color=STATUS_COLORS.get(status, FG))
        self.lbl_timer.configure(text=f"⏱ {active.elapsed():.0f}s")
        self.lbl_counts.configure(text=f"replies {st['replies']} · tool calls {st['tool_calls']}")
        self.lbl_tools.configure(text="   ".join(f"{k}×{v}" for k, v in st["tools_used"].items()))
        self._set_text(self.txt_findings, "\n".join(str(p) for p in st["paths"]) or "—")
        self._set_text(self.txt_think, self._clip(st["thinking"] or "—", 20000))
        self._set_text(self.txt_writeup, st["writeup"] or "（解题成功后自动生成）")
        # keep the full flag text (braces + prefix) untouched — never strip it
        self.lbl_flag.configure(text=st["flag"] or "—")
        # stop button only meaningful while running
        self.btn_stop.configure(state="normal" if active.is_running() else "disabled")
        self.btn_delete.configure(state="normal")
        self.bottom.grid() if active.state["done"] else self.bottom.grid_remove()

    def _animate(self) -> None:
        self.frame += 1
        spin = SPINNER[self.frame % len(SPINNER)]
        for session in self.manager.sessions:
            btn = self._rows.get(session.id)
            if not btn:
                continue
            glyph = spin if session.is_running() else STATUS_GLYPH.get(session.state["status"], "●")
            color = STATUS_COLORS.get(session.state["status"], FG)
            btn.configure(text=f"{glyph}  {session.title}", text_color=color)
        if self.manager.active and self.manager.active.is_running():
            self._refresh_panel()
        self.root.after(90, self._animate)

    def run(self) -> None:
        self.root.mainloop()
