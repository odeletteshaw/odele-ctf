"""CustomTkinter supervision console (view). Chat-app layout over a Manager:

- left rail: one button per session (a solve in its own subprocess), with a live spinner
  while running; click to switch the center conversation;
- center: the active session as real chat bubbles — agent, tool blocks, your guidance;
- right: a rich state panel (animated status, timer, tool/path findings, flag);
- bottom: guidance input for the active session.

Only rendering lives here; all agent logic is in the Session subprocess.
"""

import random
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
STATUS_COLORS = {
    "running": "#ffd166", "solved": "#79d98a", "failed": "#ff6b6b",
    "error": "#ff6b6b", "idle": "#8b94a7",
}
STATUS_GLYPH = {"solved": "✓", "failed": "✗", "error": "⚠", "idle": "○"}
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

        self.root = ctk.CTk()
        self.root.title("odele-ctf · supervision console")
        self.root.geometry("1220x760")
        self.mono = ctk.CTkFont(family="Menlo", size=12)
        self.mono_s = ctk.CTkFont(family="Menlo", size=11)
        self.bold = ctk.CTkFont(family="Menlo", size=15, weight="bold")

        self._build()
        self.root.after(poll_ms, self._poll)
        self.root.after(90, self._animate)

    # --- layout ------------------------------------------------------------
    def _build(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self._build_rail()
        self._build_center()
        self._build_right()

    def _build_rail(self) -> None:
        rail = ctk.CTkFrame(self.root, width=220, corner_radius=0)
        rail.grid(row=0, column=0, sticky="ns")
        rail.grid_propagate(False)
        ctk.CTkLabel(rail, text="SESSIONS", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 4))
        ctk.CTkButton(rail, text="＋  New session", command=self._show_setup,
                      height=34, anchor="w").pack(fill="x", padx=12, pady=(0, 8))
        self.rail_list = ctk.CTkScrollableFrame(rail, fg_color="transparent")
        self.rail_list.pack(fill="both", expand=True, padx=4)

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
                box.configure(state="disabled")  # planned categories can't be launched yet
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
        self.chal_menu.configure(values=options)
        if self.chal_menu.get() not in options:
            self.chal_menu.set(options[0])

    def _show_setup(self) -> None:
        self.manager.active = None
        for btn in self._rows.values():
            btn.configure(fg_color="transparent")
        self.center_head.configure(text="New session")
        self.chat.grid_remove()
        self.bottom.grid_remove()
        self.setup.grid()
        self._refresh_chal_options()

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
        self.setup_hint.configure(text="")
        self.setup.grid_remove()
        self.add_session(self.manager.new_session(spec, title, category))

    def _build_right(self) -> None:
        panel = ctk.CTkFrame(self.root, width=290, corner_radius=0)
        panel.grid(row=0, column=2, sticky="ns")
        panel.grid_propagate(False)
        pad = {"anchor": "w", "padx": 16}
        self.big_status = ctk.CTkLabel(panel, text="○ idle", font=self.bold, text_color=MUTED)
        self.big_status.pack(**pad, pady=(18, 0))
        self.lbl_timer = ctk.CTkLabel(panel, text="⏱ 0s", text_color=MUTED, font=self.mono)
        self.lbl_timer.pack(**pad, pady=(2, 14))
        self.lbl_counts = ctk.CTkLabel(panel, text="replies 0 · tool calls 0", font=self.mono)
        self.lbl_counts.pack(**pad)
        self.lbl_tools = ctk.CTkLabel(panel, text="", text_color=MUTED, font=self.mono_s,
                                      justify="left", wraplength=250)
        self.lbl_tools.pack(**pad, pady=(2, 14))
        ctk.CTkLabel(panel, text="FINDINGS", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(**pad)
        self.txt_findings = ctk.CTkTextbox(panel, height=110, font=self.mono_s, wrap="word")
        self.txt_findings.pack(fill="x", padx=16, pady=(4, 14))
        ctk.CTkLabel(panel, text="CURRENT THINKING", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(**pad)
        self.txt_think = ctk.CTkTextbox(panel, height=180, font=self.mono_s, wrap="word")
        self.txt_think.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        ctk.CTkLabel(panel, text="FLAG", text_color=MUTED,
                     font=ctk.CTkFont(family="Menlo", size=11, weight="bold")).pack(**pad)
        self.lbl_flag = ctk.CTkLabel(panel, text="—", text_color="#79d98a", font=self.bold)
        self.lbl_flag.pack(**pad, pady=(4, 16))

    # --- sessions ----------------------------------------------------------
    def add_session(self, session: Session) -> None:
        btn = ctk.CTkButton(self.rail_list, text=f"○  {session.title}", anchor="w",
                            fg_color="transparent", hover_color=RAIL_SEL, height=40,
                            command=lambda s=session: self.select(s))
        btn.pack(fill="x", pady=2)
        self._rows[session.id] = btn
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
            if status in ("solved", "failed", "error"):
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
        self.lbl_flag.configure(text=st["flag"] or "—")

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
