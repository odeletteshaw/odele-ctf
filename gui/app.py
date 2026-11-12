"""CustomTkinter supervision console (view). Chat-app layout over a Manager:

- left rail: folders and, under them, one button per session (a solve in its own
  subprocess), with a live spinner while running; click to switch the center conversation;
- center: the active session as real chat bubbles — agent, tool blocks, your guidance;
- right: a rich state panel (animated status, timer, tool/path findings, flag) with a stop
  button, a rename action, and copy buttons;
- bottom: guidance input for the active session.

Only rendering lives here; all agent logic is in the Session subprocess.
"""

import random
import tkinter.simpledialog as simpledialog
from urllib.parse import urlparse

import customtkinter as ctk

from typing import Any

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.catalog import CATEGORIES  # noqa: E402

from .builder import list_challenges
from .manager import Manager, Session

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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
}
STATUS_GLYPH = {"solved": "✓", "failed": "✗", "error": "⚠", "idle": "○", "cancelled": "■"}
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
MAX_OUT = 1400
WRAP = 560


class ConsoleApp:
    def __init__(self, manager: Manager, poll_ms: int = 150) -> None:
        self.manager = manager
        self.poll_ms = poll_ms
        self.frame = 0
        self._rendered: dict[int, int] = {}
        self._rows: dict[int, ctk.CTkButton] = {}
        self._inherit: dict[str, Any] | None = None

        self.root = ctk.CTk()
        self.root.title("odele-ctf · supervision console")
        self.root.geometry("1220x760")
        self.mono = ctk.CTkFont(family="Menlo", size=12)
        self.mono_s = ctk.CTkFont(family="Menlo", size=11)
        self.bold = ctk.CTkFont(family="Menlo", size=15, weight="bold")

        self._build()
        self.root.bind("<Command-c>", self._copy_flag)
        self.root.bind("<Control-c>", self._copy_flag)
        self.root.after(poll_ms, self._poll)
        self.root.after(90, self._animate)

    # --- layout ------------------------------------------------------------
    def _build(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        # rail (0) and right (3) are fixed width; center (1) fills; a draggable divider (2)
        # sits between center and right.
        self.root.grid_columnconfigure(1, weight=1)
        self._build_rail()
        self._build_center()
        self._build_divider()
        self._build_right()

    def _build_rail(self) -> None:
        rail = ctk.CTkFrame(self.root, width=230, corner_radius=0)
        rail.grid(row=0, column=0, sticky="ns")
        rail.grid_propagate(False)
        ctk.CTkLabel(rail, text="SESSIONS", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 4))
        row = ctk.CTkFrame(rail, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(row, text="＋ Session", command=self._show_setup,
                      height=32, anchor="w").pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(row, text="🗂", width=40, height=32, command=self._new_folder,
                      fg_color="#2a3648", hover_color="#35445a").pack(side="left")
        self.rail_list = ctk.CTkScrollableFrame(rail, fg_color="transparent")
        self.rail_list.pack(fill="both", expand=True, padx=4)

    def _build_divider(self) -> None:
        self.divider = ctk.CTkFrame(self.root, width=6, corner_radius=0, fg_color="#20283a",
                                    cursor="sb_h_double_arrow")
        self.divider.grid(row=0, column=2, sticky="ns")
        self.divider.grid_propagate(False)
        self.divider.bind("<Button-1>", self._drag_start)
        self.divider.bind("<B1-Motion>", self._drag_move)

    def _drag_start(self, event: Any) -> None:
        self._drag_origin = int(event.x_root)
        self._drag_width = int(self.right_panel.cget("width"))

    def _drag_move(self, event: Any) -> None:
        dx = int(event.x_root) - self._drag_origin
        new_w = max(160, min(800, self._drag_width - dx))
        self.right_panel.configure(width=new_w)

    def _build_center(self) -> None:
        wrap = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#0f1218")
        wrap.grid(row=0, column=1, sticky="nsew")
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.center_head = ctk.CTkLabel(wrap, text="", text_color=FG, font=self.bold, anchor="w")
        self.center_head.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))

        self.chat = ctk.CTkScrollableFrame(wrap, fg_color="transparent")
        self.chat.grid(row=1, column=0, sticky="nsew", padx=8)
        self.setup = self._build_setup(wrap)
        self.setup.grid(row=1, column=0, sticky="nsew")

        self.bottom = ctk.CTkFrame(wrap, corner_radius=0, fg_color="#141822")
        self.bottom.grid(row=2, column=0, sticky="ew")
        self.entry = ctk.CTkEntry(self.bottom, placeholder_text="give the agent a hint or correction…",
                                  font=self.mono, height=38)
        self.entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)
        self.entry.bind("<Return>", lambda _e: self._send())
        ctk.CTkButton(self.bottom, text="Send guidance", command=self._send, width=130,
                      height=38).pack(side="left", padx=(0, 12), pady=10)

        self._show_setup()

    def _build_setup(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        card = ctk.CTkFrame(wrap, fg_color="#141a24", corner_radius=14)
        card.pack(padx=48, pady=28, fill="x", anchor="n")
        hf = ctk.CTkFont(family="Menlo", size=11, weight="bold")
        ctk.CTkLabel(card, text="Start a new session", font=self.bold).pack(
            anchor="w", padx=26, pady=(22, 2))
        ctk.CTkLabel(card, text="Pick the direction(s). The specific challenge can stay unknown.",
                     text_color=MUTED, font=self.mono_s).pack(anchor="w", padx=26, pady=(0, 14))

        ctk.CTkLabel(card, text="DIRECTION   (multi-select)", text_color=MUTED, font=hf).pack(
            anchor="w", padx=26)
        drow = ctk.CTkFrame(card, fg_color="transparent")
        drow.pack(anchor="w", padx=22, pady=(8, 14))
        self.dir_boxes: dict[str, ctk.CTkCheckBox] = {}
        for cat, meta in CATEGORIES.items():
            ready = meta["status"] == "ready"
            label = cat if ready else f"{cat} (soon)"
            box = ctk.CTkCheckBox(drow, text=label, command=self._refresh_chal_options, width=108)
            if not ready:
                box.configure(state="disabled")
            box.pack(side="left", padx=6, pady=3)
            self.dir_boxes[cat] = box
        self.dir_boxes["web"].select()

        ctk.CTkLabel(card, text="TARGET", text_color=MUTED, font=hf).pack(anchor="w", padx=26)
        self.mode_btn = ctk.CTkSegmentedButton(card, values=["Benchmark", "Custom URL"],
                                               command=lambda _v: self._mode_changed())
        self.mode_btn.set("Benchmark")
        self.mode_btn.pack(anchor="w", padx=26, pady=(8, 10))

        self.panel_area = ctk.CTkFrame(card, fg_color="transparent")
        self.panel_area.pack(anchor="w", padx=26, fill="x")
        self.bench_panel = ctk.CTkFrame(self.panel_area, fg_color="transparent")
        ctk.CTkLabel(self.bench_panel, text="challenge  ·  random = let the agent discover it",
                     text_color=MUTED, font=self.mono_s).pack(anchor="w")
        self.chal_menu = ctk.CTkOptionMenu(self.bench_panel, values=["🎲  random (unknown)"], width=380)
        self.chal_menu.pack(anchor="w", pady=(6, 0))
        self.custom_panel = ctk.CTkFrame(self.panel_area, fg_color="transparent")
        self.url_entry = ctk.CTkEntry(self.custom_panel, placeholder_text="https://target.ctf/…",
                                      width=440, font=self.mono)
        self.url_entry.pack(anchor="w", pady=4)
        self.desc_entry = ctk.CTkEntry(self.custom_panel, placeholder_text="description / hint (optional)",
                                       width=440, font=self.mono)
        self.desc_entry.pack(anchor="w", pady=4)
        self.flag_entry = ctk.CTkEntry(self.custom_panel,
                                       placeholder_text="flag prefix (optional, default 'flag')",
                                       width=280, font=self.mono)
        self.flag_entry.pack(anchor="w", pady=4)
        self.bench_panel.pack(anchor="w")

        # --- name + folder (new) ------------------------------------------
        opt_row = ctk.CTkFrame(card, fg_color="transparent")
        opt_row.pack(anchor="w", padx=26, pady=(14, 0))
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

        self.setup_hint = ctk.CTkLabel(card, text="", text_color="#ff6b6b", font=self.mono_s)
        self.setup_hint.pack(anchor="w", padx=26, pady=(10, 0))
        ctk.CTkButton(card, text="Start  ▶", command=self._start_from_setup,
                      height=42, width=150).pack(anchor="w", padx=26, pady=(8, 22))
        return wrap

    def _mode_changed(self) -> None:
        custom = self.mode_btn.get() == "Custom URL"
        (self.bench_panel if custom else self.custom_panel).pack_forget()
        (self.custom_panel if custom else self.bench_panel).pack(anchor="w")

    def _selected_dirs(self) -> list[str]:
        return [cat for cat, box in self.dir_boxes.items() if box.get()]

    def _refresh_chal_options(self) -> None:
        options = ["🎲  random (unknown)"]
        for cat in self._selected_dirs():
            options += [f"{cat}/{name}" for name in list_challenges(cat)]
        self._chal_options = options
        self.chal_menu.configure(values=options)
        if self.chal_menu.get() not in options:
            self.chal_menu.set(options[0])

    def _refresh_folder_options(self) -> None:
        self.folder_menu.configure(values=["(none)"] + self.manager.folders)
        if self.folder_menu.get() not in ["(none)"] + self.manager.folders:
            self.folder_menu.set("(none)")

    def _show_setup(self) -> None:
        self.manager.active = None
        for btn in self._rows.values():
            btn.configure(fg_color="transparent")
        self.center_head.configure(text="New session")
        self.chat.grid_remove()
        self.bottom.grid_remove()
        self.setup.grid()
        self._refresh_chal_options()
        self._refresh_folder_options()

    def _start_from_setup(self) -> None:
        if self.mode_btn.get() == "Custom URL":
            url = self.url_entry.get().strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                self.setup_hint.configure(text="enter a target URL starting with http:// or https://")
                return
            spec = {"kind": "custom", "url": url, "description": self.desc_entry.get().strip(),
                    "flag_prefix": self.flag_entry.get().strip() or "flag"}
            title = urlparse(url).netloc or url[:28]
            category = "custom"
        else:
            dirs = self._selected_dirs()
            if not dirs:
                self.setup_hint.configure(text="pick at least one direction")
                return
            choice = self.chal_menu.get()
            if choice.startswith("🎲"):
                category, name = random.choice([(c, n) for c in dirs for n in list_challenges(c)])
            else:
                category, name = choice.split("/", 1)
            spec = {"kind": "benchmark", "category": category, "name": name}
            title = name
        custom_name = self.name_entry.get().strip()
        if custom_name:
            title = custom_name
        folder = self.folder_menu.get()
        folder = None if folder == "(none)" else folder
        try:
            spec["max_turns"] = max(1, int(self.turns_entry.get().strip() or "100"))
        except ValueError:
            spec["max_turns"] = 100
        if self._inherit:
            spec["context"] = self._inherit["context"]
            self._inherit = None
        self.setup_hint.configure(text="")
        self.setup.grid_remove()
        self.add_session(self.manager.new_session(spec, title, category, folder=folder))

    def _build_right(self) -> None:
        self.right_panel = ctk.CTkFrame(self.root, width=290, corner_radius=0)
        self.right_panel.grid(row=0, column=3, sticky="ns")
        self.right_panel.grid_propagate(False)
        panel = self.right_panel
        pad = {"anchor": "w", "padx": 16}

        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 0))
        self.big_status = ctk.CTkLabel(top, text="○ idle", font=self.bold, text_color=MUTED)
        self.big_status.pack(side="left", anchor="w")
        self.btn_stop = ctk.CTkButton(top, text="■ Stop", width=72, height=30,
                                      fg_color="#5a2b2b", hover_color="#703636",
                                      command=self._stop_active)
        self.btn_stop.pack(side="right")
        self.lbl_timer = ctk.CTkLabel(panel, text="⏱ 0s", text_color=MUTED, font=self.mono)
        self.lbl_timer.pack(**pad, pady=(2, 6))
        self.btn_rename = ctk.CTkButton(panel, text="✎ Rename session", width=150, height=28,
                                        command=self._rename_active, anchor="w")
        self.btn_rename.pack(anchor="w", padx=16, pady=(0, 6))
        self.btn_continue = ctk.CTkButton(panel, text="↻ Continue (inherit)", width=170, height=28,
                                          command=self._continue_active, anchor="w")
        self.btn_continue.pack(anchor="w", padx=16, pady=(0, 8))
        self.lbl_counts = ctk.CTkLabel(panel, text="replies 0 · tool calls 0", font=self.mono)
        self.lbl_counts.pack(**pad)
        self.lbl_tools = ctk.CTkLabel(panel, text="", text_color=MUTED, font=self.mono_s,
                                      justify="left", wraplength=250)
        self.lbl_tools.pack(**pad, pady=(2, 14))

        self._header(panel, "FINDINGS", lambda: self._copy(self._findings_text()))
        self.txt_findings = ctk.CTkTextbox(panel, height=110, font=self.mono_s, wrap="word")
        self.txt_findings.pack(fill="x", padx=16, pady=(4, 14))
        self._wheel_scroll(self.txt_findings)

        self._header(panel, "CURRENT THINKING", lambda: self._copy(self._thinking_text()))
        self.txt_think = ctk.CTkTextbox(panel, height=180, font=self.mono_s, wrap="word")
        self.txt_think.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        self._wheel_scroll(self.txt_think)

        flag_row = ctk.CTkFrame(panel, fg_color="transparent")
        flag_row.pack(fill="x", padx=16, pady=(4, 16))
        ctk.CTkLabel(flag_row, text="FLAG", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(side="left")
        self.lbl_flag = ctk.CTkLabel(flag_row, text="—", text_color="#79d98a", font=self.bold,
                                     anchor="w", justify="left", wraplength=200)
        self.lbl_flag.pack(side="left", padx=(8, 0), expand=True, fill="x")
        self._copy_btn(flag_row, lambda: self._copy(self._flag_now()))

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

    # --- sessions / folders ------------------------------------------------
    def _new_folder(self) -> None:
        name = simpledialog.askstring("New folder", "Folder name:", parent=self.root)
        if name and self.manager.new_folder(name):
            self._render_rail()

    def _render_rail(self) -> None:
        for child in self.rail_list.winfo_children():
            child.destroy()
        self._rows.clear()
        for folder in self.manager.folders:
            self._folder_label(folder)
            for s in self.manager.sessions:
                if s.folder == folder:
                    self._session_button(s, indent=True)
        for s in self.manager.sessions:
            if s.folder is None:
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
        self._rows[session.id] = btn

    def add_session(self, session: Session) -> None:
        self._render_rail()
        self._rendered.setdefault(session.id, 0)
        self.select(session)

    def select(self, session: Session) -> None:
        self.manager.active = session
        self.setup.grid_remove()
        self.chat.grid()
        self.bottom.grid()
        for sid, btn in self._rows.items():
            btn.configure(fg_color=RAIL_SEL if sid == session.id else "transparent")
        self.center_head.configure(text=f"{session.title}  ·  {session.category}", text_color=FG)
        for child in self.chat.winfo_children():
            child.destroy()
        self._rendered[session.id] = 0
        for ev in session.transcript:
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
        ctk.CTkLabel(bubble, text=text, justify="center" if anchor == "center" else "left",
                     wraplength=WRAP if not full else 640, text_color=text_color,
                     font=font or self.mono).pack(
            padx=12, pady=8, anchor="center" if anchor == "center" else "w")
        self._scroll_bottom()

    def _scroll_bottom(self) -> None:
        try:
            self.chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _render(self, ev: dict[str, Any]) -> None:
        kind = ev.get("type")
        if kind == "agent":
            self._bubble("w", AGENT_BG, f"🧠  {ev['text']}")
        elif kind == "tool_call":
            self._bubble("w", TOOL_BG, f"⚙  {ev['name']}  {ev.get('args', '')}",
                         text_color=TOOL_FG, font=self.mono_s, full=True)
        elif kind == "tool_result":
            out = ev.get("output", "")
            if len(out) > MAX_OUT:
                out = out[:MAX_OUT] + f"  …(+{len(out) - MAX_OUT})"
            self._bubble("w", RESULT_BG, f"↳ {out}", text_color=MUTED, font=self.mono_s, full=True)
        elif kind == "guidance":
            self._bubble("e", GUIDE_BG, f"you ▸ {ev['text']}", text_color=GUIDE_FG)
        elif kind == "status":
            status = ev.get("status", "")
            if status in ("solved", "failed", "error", "cancelled"):
                extra = ev.get("flag") or ev.get("error") or ""
                self._bubble("center", "#11151c", f"— {status.upper()} {extra} —".strip(),
                             text_color=STATUS_COLORS.get(status, FG), font=self.mono, full=True)

    # --- behavior ----------------------------------------------------------
    def _send(self) -> None:
        text = self.entry.get().strip()
        if text and self.manager.active:
            self.manager.active.send_guidance(text)
            self._bubble("e", GUIDE_BG, f"you ▸ {text}  (queued)", text_color=GUIDE_FG)
            self.entry.delete(0, "end")

    def _stop_active(self) -> None:
        if self.manager.active and self.manager.active.is_running():
            self.manager.stop(self.manager.active)
            self._bubble("center", "#11151c", "— CANCELLED —", text_color=STATUS_COLORS["cancelled"],
                         font=self.mono, full=True)
            self._refresh_panel()

    def _rename_active(self) -> None:
        if not self.manager.active:
            return
        name = simpledialog.askstring("Rename session", "Session name:",
                                      initialvalue=self.manager.active.title, parent=self.root)
        if name:
            self.manager.rename(self.manager.active, name)
            self.center_head.configure(text=f"{self.manager.active.title}  ·  {self.manager.active.category}")
            self._render_rail()

    def _format_transcript(self, transcript: list[dict[str, Any]]) -> str:
        lines = [
            "A previous session already worked on this target. Here is its transcript — "
            "continue from where it left off, do NOT redo work already done, and pick up the "
            "most promising thread.\n"
        ]
        for ev in transcript:
            kind = ev.get("type")
            if kind == "agent":
                lines.append(f"[agent] {ev.get('text', '')}")
            elif kind == "tool_call":
                lines.append(f"[tool {ev.get('name', '?')}] {ev.get('args', '')}")
            elif kind == "tool_result":
                out = ev.get("output", "")
                if len(out) > 500:
                    out = out[:500] + " …"
                lines.append(f"[result] {out}")
            elif kind == "guidance":
                lines.append(f"[you] {ev.get('text', '')}")
            elif kind == "status":
                extra = ev.get("flag") or ev.get("error") or ""
                lines.append(f"[status] {ev.get('status', '')} {extra}".strip())
        return "\n".join(lines)

    def _continue_active(self) -> None:
        session = self.manager.active
        if not session:
            return
        self._inherit = {
            "context": self._format_transcript(session.transcript),
            "spec": dict(session.spec),
        }
        self._show_setup()
        self._prefill_setup(session.spec, session.title)
        if session.folder and session.folder in self.manager.folders:
            self.folder_menu.set(session.folder)

    def _prefill_setup(self, spec: dict[str, Any], title: str) -> None:
        if spec.get("kind") == "custom":
            self.mode_btn.set("Custom URL")
            self._mode_changed()
            self.url_entry.delete(0, "end"); self.url_entry.insert(0, spec.get("url", ""))
            self.desc_entry.delete(0, "end"); self.desc_entry.insert(0, spec.get("description", ""))
            self.flag_entry.delete(0, "end"); self.flag_entry.insert(0, spec.get("flag_prefix", "flag"))
        else:
            self.mode_btn.set("Benchmark")
            self._mode_changed()
            cat = spec.get("category", "")
            for c, box in self.dir_boxes.items():
                box.select() if c == cat else box.deselect()
            self._refresh_chal_options()
            opt = f"{cat}/{spec.get('name', '')}"
            if opt in self._chal_options:
                self.chal_menu.set(opt)
        self.turns_entry.delete(0, "end"); self.turns_entry.insert(0, str(spec.get("max_turns", 100)))
        self.name_entry.delete(0, "end"); self.name_entry.insert(0, title)

    def _copy(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _copy_flag(self, _event=None) -> None:
        w = self.root.focus_get()
        if isinstance(w, (ctk.CTkTextbox, ctk.CTkEntry)):
            return  # textbox/entry handles its own copy
        if self.manager.active and self.manager.active.state.get("flag"):
            self._copy(self.manager.active.state["flag"])

    def _findings_text(self) -> str:
        return self.txt_findings.get("1.0", "end").strip()

    def _thinking_text(self) -> str:
        return self.txt_think.get("1.0", "end").strip()

    def _set_text(self, box: ctk.CTkTextbox, text: str) -> None:
        box.delete("1.0", "end")
        box.insert("end", text)

    def _poll(self) -> None:
        self.manager.drain_all()
        active = self.manager.active
        if active:
            start = self._rendered.get(active.id, 0)
            for ev in active.transcript[start:]:
                self._render(ev)
            self._rendered[active.id] = len(active.transcript)
            self._refresh_panel()
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
        self._set_text(self.txt_findings, "\n".join(st["paths"]) or "—")
        self._set_text(self.txt_think, st["thinking"] or "—")
        # keep the full flag text (braces + prefix) untouched — never strip it
        self.lbl_flag.configure(text=st["flag"] or "—")
        # stop button only meaningful while running
        self.btn_stop.configure(state="normal" if active.is_running() else "disabled")

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
