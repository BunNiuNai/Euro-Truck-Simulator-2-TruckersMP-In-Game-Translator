"""
Translation display window — modern frosted-glass overlay.
Four-section vertical layout: accent line → header → messages → stats → shortcuts.
Borderless with Win32 acrylic/mica blur and 1px blue border.
"""
from __future__ import annotations

import ctypes
import os
import re
import threading
import time
import tkinter as tk
from datetime import datetime, timezone, timedelta
from queue import Queue, Empty
from tkinter import ttk

from config import AppConfig, VERSION, save_config
from message_types import DisplayMessage, TranslationStats
from win32_constants import (
    GWL_EXSTYLE, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW,
    HOTKEY_SEND_ID,
    MOD_SHIFT, MOD_CONTROL, MOD_ALT,
    VK_SHIFT, VK_CONTROL, VK_ALT,
    SPECIAL_VK, KEY_NAME_MAP,
    POINT, mod_vk,
)
from logger import get_logger

# ── Color palette (dark tech theme) ──
# Three-tier blue system:
ACCENT       = "#4494FC"   # 主色调蓝 — 顶部高亮条、标题栏 accent line
BORDER_BLUE  = "#60A8FF"   # 描边线蓝 — 窗口外边框、内部分隔线
HIGHLIGHT    = "#70B8FF"   # 高亮文字蓝 — 用户名、交互控件选中态

BG       = "#000000"   # pure black (colorless — acrylic blur shows through)
FG       = "#cccccc"    # primary text
FG_DIM   = "#858585"    # muted/dim text
FG_TIMESTAMP = "#666666"  # timestamp text
FG_STATS_NUM = ACCENT    # stats numbers (core blue)
FG_STATS_LABEL = FG_DIM  # stats labels
PLAYER   = HIGHLIGHT     # player name (highlight blue)
SYS_GRAY = "#858585"     # system messages
TRANSL   = "#FFD700"     # gold translation output
SEP      = BORDER_BLUE   # separator lines (border blue)
BORDER   = BORDER_BLUE   # window outer border
CARD_BG  = "#151515"     # card elements (slightly lighter than pure black)
STATS_BG = "#111111"     # stats bar background
SELF_GREEN = "#4ec9b0"   # self-message prefix
ERROR_RED  = "#f44747"   # error/baidu fix
NOTICE_BG  = "#2a2a2a"
ENTRY_BG   = "#1e1e1e"   # input entry background

# Debug logging — off by default
_debug_enabled = False


def set_debug_enabled(enabled: bool) -> None:
    global _debug_enabled
    _debug_enabled = enabled


def _debug_log(msg: str) -> None:
    if not _debug_enabled:
        return
    try:
        log_path = os.path.join(os.environ.get("TEMP", "."), "ets2_translator_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} [{os.getpid()}] {msg}\n")
    except Exception:
        pass


class OverlayWindow:
    """Tkinter borderless overlay window with frosted glass effect."""

    def __init__(self, cfg: AppConfig, message_queue: Queue, stats_ref=None,
                 server_name_ref: dict | None = None):
        self.cfg = cfg
        self.queue = message_queue
        self.stats_ref = stats_ref or {}
        self._server_name_ref = server_name_ref or {"name": ""}
        self.root = tk.Tk()
        self.root.title(f"ETS2 聊天翻译器 {VERSION}")
        self.root.configure(bg=BG)
        self._messages = []    # list of (player, orig, trans, is_self, detected_lang, timestamp, is_system)
        self._displayed_count = 0
        self._is_overlay = False
        self._edge_code = ""
        self._save_pos_after = None
        self._ready = False
        self._setup_ui()
        self._apply_mode()
        self._restore_or_center()
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.after(1000, lambda: setattr(self, "_ready", True))
        # Apply acrylic with retries — window may not be fully rendered yet
        self.root.after(200, self._apply_acrylic)
        self.root.after(800, self._apply_acrylic)   # retry: DWM may need window fully painted
        self.root.after(2000, self._apply_acrylic)  # final retry for slow systems
        # Re-apply on window map (e.g. after hide/show)
        self.root.bind("<Map>", lambda e: self.root.after(100, self._apply_acrylic))
        # Start hotkey poller
        self.root.after(500, self._start_hotkey_poller)
        # Start server name polling
        self.root.after(2000, self._poll_server_name)

    # ═══════════════════════════════════════════════════════════════
    #  UI construction
    # ═══════════════════════════════════════════════════════════════

    def _setup_ui(self):
        """Build the four-section grid layout inside a 1px blue border wrapper."""
        # Outer wrapper — provides the 1px blue border
        self._border_frame = tk.Frame(self.root, bg=BORDER, bd=0, highlightthickness=0)
        self._border_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Inner container — all content lives here
        self.outer = tk.Frame(self._border_frame, bg=BG, bd=0, highlightthickness=0)
        self.outer.pack(fill=tk.BOTH, expand=True)

        # Grid: row 0=accent, 1=header, 2=separator,
        #       3=messages (weighted), 4=input_area, 5=separator, 6=stats+shortcuts
        self.outer.rowconfigure(0, weight=0)  # accent line
        self.outer.rowconfigure(1, weight=0)  # header (compact: version+server+time)
        self.outer.rowconfigure(2, weight=0)  # separator
        self.outer.rowconfigure(3, weight=1)  # messages (takes remaining space)
        self.outer.rowconfigure(4, weight=0)  # input area (hidden by default)
        self.outer.rowconfigure(5, weight=0)  # separator
        self.outer.rowconfigure(6, weight=0)  # stats bar (counts left, shortcuts right)
        self.outer.columnconfigure(0, weight=1)

        row = 0

        # Row 0: Blue accent line (2px)
        self.accent_line = tk.Frame(self.outer, bg=ACCENT, height=2)
        self.accent_line.grid(row=row, column=0, sticky="ew")
        self.accent_line.grid_propagate(False)
        row += 1

        # Row 1: Compact header (version + server left, time right)
        self._build_header(row)
        row += 1

        # Row 2: Separator below header
        sep1 = tk.Frame(self.outer, bg=SEP, height=1)
        sep1.grid(row=row, column=0, sticky="ew", padx=10)
        row += 1

        # Row 3: Message area (scrollable text widget)
        self._build_message_area(row)
        row += 1

        # Row 4: Input area (between messages and stats)
        self._build_input_area(row)
        row += 1

        # Row 5: Separator above stats
        sep2 = tk.Frame(self.outer, bg=SEP, height=1)
        sep2.grid(row=row, column=0, sticky="ew", padx=10)
        row += 1

        # Row 6: Stats bar (counts left, shortcuts right — same row)
        self._build_stats_bar(row)

        # ── Context menu ──
        self._build_context_menu()

        # ── Overlay-mode mouse handlers for drag & resize ──
        for w in (self._border_frame, self.outer, self.accent_line):
            w.bind("<Button-1>", self._on_mouse_down)
            w.bind("<B1-Motion>", self._on_mouse_move)
            w.bind("<Motion>", self._on_mouse_hover)
            w.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Callback stubs (set by main.py)
        self._settings_cb = None
        self._switch_mode_cb = None
        self._exit_cb = None

    def _build_header(self, row: int):
        """Ultra-compact header: version + server name on one line left, time right."""
        frame = tk.Frame(self.outer, bg=BG)
        frame.grid(row=row, column=0, sticky="ew", padx=12, pady=(2, 1))
        frame.columnconfigure(0, weight=1)

        # Left: version + server name on the same line
        left = tk.Frame(frame, bg=BG)
        left.grid(row=0, column=0, sticky="w")

        self.version_label = tk.Label(
            left, text=VERSION, bg=BG, fg=FG,
            font=("Microsoft YaHei", 9, "bold"), anchor=tk.W,
        )
        self.version_label.pack(side=tk.LEFT)

        tk.Label(left, text=" · ", bg=BG, fg=FG_DIM,
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        self.server_label = tk.Label(
            left, text="等待服务器连接...", bg=BG, fg=FG_DIM,
            font=("Microsoft YaHei", 9), anchor=tk.W,
        )
        self.server_label.pack(side=tk.LEFT)

        # Bind header for dragging
        for w in (frame, left, self.version_label, self.server_label):
            w.bind("<Button-1>", self._on_mouse_down)
            w.bind("<B1-Motion>", self._on_mouse_move)
            w.bind("<Motion>", self._on_mouse_hover)
            w.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Right: Beijing time
        self._header_time_label = tk.Label(
            frame, text="", bg=BG, fg=FG_DIM,
            font=("Microsoft YaHei", 9), anchor=tk.E,
        )
        self._header_time_label.grid(row=0, column=1, sticky="e")
        self._update_header_clock()

    def _build_message_area(self, row: int):
        text_frame = tk.Frame(self.outer, bg=BG)
        text_frame.grid(row=row, column=0, sticky="nsew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame,
            font=("Microsoft YaHei", self.cfg.font_size),
            bg=BG, fg=FG,
            wrap=tk.WORD, state=tk.DISABLED,
            borderwidth=0, highlightthickness=0,
            padx=10, pady=6, insertbackground=FG,
        )
        vbar = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=vbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")

        # Text widget mouse handlers for drag & right-click
        self.text.bind("<Button-1>", self._on_mouse_down)
        self.text.bind("<B1-Motion>", self._on_mouse_move)
        self.text.bind("<Motion>", self._on_mouse_hover)
        self.text.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Color/text tags
        self._setup_text_tags()

    def _setup_text_tags(self):
        fs = self.cfg.font_size
        self.text.tag_configure("player", foreground=PLAYER,
                                font=("Microsoft YaHei", fs, "bold"))
        self.text.tag_configure("timestamp", foreground=FG_TIMESTAMP,
                                font=("Microsoft YaHei", max(8, fs - 1)))
        self.text.tag_configure("translation", foreground=TRANSL,
                                font=("Microsoft YaHei", fs))
        self.text.tag_configure("original", foreground=FG_DIM,
                                font=("Microsoft YaHei", max(8, fs - 2)))
        self.text.tag_configure("system_text", foreground=SYS_GRAY,
                                font=("Microsoft YaHei", max(8, fs - 1)))
        self.text.tag_configure("self_prefix", foreground=SELF_GREEN,
                                font=("Microsoft YaHei", fs, "bold"))
        self.text.tag_configure("error", foreground=ERROR_RED,
                                font=("Microsoft YaHei", fs))
        self.text.tag_configure("sent_prefix", foreground=SELF_GREEN,
                                font=("Microsoft YaHei", fs, "bold"))
        self.text.tag_configure("separator", foreground=SEP,
                                font=("Microsoft YaHei", max(6, fs - 6)))

    def _build_stats_bar(self, row: int):
        """Stats bar: translation counts left, shortcuts text right."""
        frame = tk.Frame(self.outer, bg=STATS_BG)
        frame.grid(row=row, column=0, sticky="ew", padx=10, pady=(1, 3))
        frame.columnconfigure(0, weight=1)  # left spacer pushes right side

        def _make_stat(parent, label_text):
            """Create (label, number) pair."""
            f = tk.Frame(parent, bg=STATS_BG)
            f.pack(side=tk.LEFT, padx=8)
            lb = tk.Label(f, text=label_text, bg=STATS_BG, fg=FG_STATS_LABEL,
                          font=("Microsoft YaHei", 9))
            lb.pack(side=tk.LEFT)
            num = tk.Label(f, text="0", bg=STATS_BG, fg=FG_STATS_NUM,
                           font=("Microsoft YaHei", 9, "bold"))
            num.pack(side=tk.LEFT, padx=(2, 0))
            return num

        self._stat_translated = _make_stat(frame, "已翻译:")
        self._stat_cached = _make_stat(frame, "命中:")
        self._stat_saved = _make_stat(frame, "节省:")

        # Shortcuts text on the right side
        shortcuts = [
            f"{self._format_hotkey(self.cfg.send_hotkey)} 呼出",
            "Enter 发送",
        ]
        text = "  |  ".join(shortcuts)
        self.shortcuts_label = tk.Label(
            frame, text=text, bg=STATS_BG, fg=FG_DIM,
            font=("Microsoft YaHei", 8), anchor=tk.E,
        )
        self.shortcuts_label.pack(side=tk.RIGHT, padx=8)

    def _build_input_area(self, row: int):
        """Input frame between messages and stats bar. Always visible."""
        self.input_frame = tk.Frame(self.outer, bg=CARD_BG)
        self.input_frame.grid(row=row, column=0, sticky="ew", padx=10, pady=(2, 2))

        # Notice label
        self.notice_label = tk.Label(
            self.input_frame, text="", bg=NOTICE_BG, fg=ERROR_RED,
            font=("Microsoft YaHei", 10, "bold"), anchor=tk.CENTER, height=1,
        )
        self._notice_after = None

        # Entry row
        self.entry_row = tk.Frame(self.input_frame, bg=CARD_BG)
        self.entry_row.pack(fill=tk.X, padx=8, pady=(2, 3))

        self.send_entry = tk.Entry(
            self.entry_row, font=("Microsoft YaHei", self.cfg.font_size),
            bg=ENTRY_BG, fg=FG, insertbackground=FG,
            relief=tk.FLAT, borderwidth=0,
        )
        self.send_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        self.send_hint = tk.Label(
            self.entry_row, text=" 输入中文后回车 ", bg=CARD_BG, fg=FG_DIM,
            font=("Microsoft YaHei", 9),
        )
        self.send_hint.pack(side=tk.RIGHT, padx=(6, 0))

        self.send_entry.bind("<Return>", self._on_send_enter)
        self.send_entry.bind("<Escape>", lambda e: (
            self.send_entry.delete(0, tk.END), self._hide_input()
        ))
        self.send_entry.bind("<FocusOut>", lambda e: None)  # keep focus

        # Sending state
        self._sending = False
        self._pending_chinese = ""
        self._pending_english = ""

    def _build_context_menu(self):
        self.ctx_menu = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG)
        self.ctx_menu.add_command(label="Settings / 设置", command=self._on_settings)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Exit / 退出", command=self._on_exit)
        self.text.bind("<Button-3>", lambda e: self.ctx_menu.tk_popup(e.x_root, e.y_root))

    # ═══════════════════════════════════════════════════════════════
    #  Acrylic / Mica effect
    # ═══════════════════════════════════════════════════════════════

    def _apply_acrylic(self):
        """Try to apply Win32 acrylic/mica frosted glass. Idempotent — safe to call repeatedly."""
        if getattr(self, '_acrylic_applied', False):
            return  # already succeeded, skip
        try:
            self.root.update_idletasks()  # ensure window is fully realized
            from acrylic_helper import apply_acrylic
            ok = apply_acrylic(self.root, effect="auto", gradient_color=0x75222222)
            if ok:
                self._acrylic_applied = True
                self.root.update_idletasks()  # force DWM to pick up the change
                log = get_logger()
                if log:
                    log.info("SYS", "亚克力/云母效果已应用")
                return
        except Exception as e:
            log = get_logger()
            if log:
                log.warn("SYS", f"亚克力效果失败: {e}")
        # Fallback: use opaque window (NOT -alpha — that causes ghosting on layered windows).
        # The window will be solid black which still looks acceptable.
        self._acrylic_applied = True  # prevent retries that cause flicker
        self.root.attributes("-alpha", 1.0)

    # ═══════════════════════════════════════════════════════════════
    #  Window mode, position, corners
    # ═══════════════════════════════════════════════════════════════

    def _restore_or_center(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if self.cfg.win_w > 0 and self.cfg.win_h > 0 and self.cfg.win_x >= 0 and self.cfg.win_y >= 0:
            x = max(0, min(self.cfg.win_x, sw - 100))
            y = max(0, min(self.cfg.win_y, sh - 100))
            w = min(self.cfg.win_w, sw)
            h = min(self.cfg.win_h, sh)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            w = self.cfg.win_w if self.cfg.win_w > 0 else 620
            h = self.cfg.win_h if self.cfg.win_h > 0 else 400
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _save_position(self):
        if self.root.state() == "withdrawn":
            return
        try:
            g = self.root.winfo_geometry()
            m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", g)
            if m:
                self.cfg.win_w = int(m.group(1))
                self.cfg.win_h = int(m.group(2))
                self.cfg.win_x = int(m.group(3))
                self.cfg.win_y = int(m.group(4))
        except (ValueError, IndexError, AttributeError):
            return

    def _schedule_save_position(self):
        if not self._ready:
            return
        if self._save_pos_after:
            self.root.after_cancel(self._save_pos_after)
        self._save_pos_after = self.root.after(1000, self._do_save_position)

    def _do_save_position(self) -> None:
        self._save_pos_after = None
        self._save_position()
        save_config(self.cfg)

    def _apply_mode(self):
        """Apply window mode: always borderless overlay with acrylic or alpha."""
        self.root.attributes("-topmost", True)
        self._is_overlay = True
        self.root.resizable(False, False)
        self.root.minsize(280, 250)
        self.root.overrideredirect(True)
        self.root.update_idletasks()
        # WS_EX_TOOLWINDOW: hide from taskbar
        ex = ctypes.windll.user32.GetWindowLongPtrW(self.root.winfo_id(), GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongPtrW(self.root.winfo_id(), GWL_EXSTYLE, ex | WS_EX_TOOLWINDOW)
        self._set_click_through(self.cfg.click_through)

    def _set_click_through(self, enable: bool):
        hwnd = self.root.winfo_id()
        ex = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        if enable:
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT)
        else:
            ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_TRANSPARENT)

    def _toggle_mode(self):
        if self._switch_mode_cb:
            self._switch_mode_cb()

    def _on_settings(self):
        if self._settings_cb:
            self._settings_cb()

    def _on_exit(self):
        if self._exit_cb:
            self._exit_cb()

    # ═══════════════════════════════════════════════════════════════
    #  Mouse drag & resize (borderless window)
    # ═══════════════════════════════════════════════════════════════

    BORDER = 8
    MIN_W, MIN_H = 280, 250

    CURSORS = {
        "n":  "size_ns",      "s":  "size_ns",
        "w":  "size_we",      "e":  "size_we",
        "nw": "size_nw_se",   "se": "size_nw_se",
        "ne": "size_ne_sw",   "sw": "size_ne_sw",
    }

    def _win_xy(self, event):
        return event.x_root - self.root.winfo_rootx(), event.y_root - self.root.winfo_rooty()

    def _edge(self, wx, wy):
        w, h = self.root.winfo_width(), self.root.winfo_height()
        e = ""
        if wx <= self.BORDER: e += "w"
        elif wx >= w - self.BORDER: e += "e"
        if wy <= self.BORDER: e += "n"
        elif wy >= h - self.BORDER: e += "s"
        return e

    def _on_mouse_hover(self, event):
        wx, wy = self._win_xy(event)
        edge = self._edge(wx, wy)
        c = self.CURSORS.get(edge, "")
        self.outer.configure(cursor=c)
        try:
            self._border_frame.configure(cursor=c if c else "fleur")
        except Exception:
            pass

    def _on_mouse_down(self, event):
        wx, wy = self._win_xy(event)
        self._edge_code = self._edge(wx, wy)
        self._mx = event.x_root
        self._my = event.y_root
        if not self._edge_code:
            self._start_x = self.root.winfo_x()
            self._start_y = self.root.winfo_y()

    def _on_mouse_up(self, event):
        self._edge_code = ""

    def _on_mouse_move(self, event):
        dx = event.x_root - self._mx
        dy = event.y_root - self._my

        if self._edge_code:
            x, y = self.root.winfo_x(), self.root.winfo_y()
            w, h = self.root.winfo_width(), self.root.winfo_height()
            if "e" in self._edge_code: w = max(self.MIN_W, w + dx)
            if "s" in self._edge_code: h = max(self.MIN_H, h + dy)
            if "w" in self._edge_code:
                nw = max(self.MIN_W, w - dx)
                x += w - nw
                w = nw
            if "n" in self._edge_code:
                nh = max(self.MIN_H, h - dy)
                y += h - nh
                h = nh
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._mx = event.x_root
            self._my = event.y_root
            self._schedule_save_position()
        else:
            x = self._start_x + event.x_root - self._mx
            y = self._start_y + event.y_root - self._my
            self.root.geometry(f"+{x}+{y}")
            self._schedule_save_position()

    # ═══════════════════════════════════════════════════════════════
    #  Clock
    # ═══════════════════════════════════════════════════════════════

    def _update_header_clock(self):
        beijing = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        self._header_time_label.config(text=beijing.strftime("%H:%M:%S"))
        self.root.after(1000, self._update_header_clock)

    def _update_stats_display(self):
        """Update stats numbers in the stats bar."""
        if not self.stats_ref:
            return
        if isinstance(self.stats_ref, TranslationStats):
            stats = self.stats_ref
        else:
            stats = TranslationStats(
                translated=self.stats_ref.get("translated", 0),
                cached=self.stats_ref.get("cached", 0),
                self_skipped=self.stats_ref.get("self", 0),
            )
        self._stat_translated.config(text=str(stats.translated))
        self._stat_cached.config(text=str(stats.cached))
        self._stat_saved.config(text=stats.savings_pct())

    # ═══════════════════════════════════════════════════════════════
    #  Server name polling
    # ═══════════════════════════════════════════════════════════════

    def _poll_server_name(self):
        """Periodically read server name from the shared ref (set by monitor)."""
        name = self._server_name_ref.get("name", "")
        current = self.server_label.cget("text")
        if name and name != current:
            self.server_label.config(text=name, fg=ACCENT)
        elif not name and current != "等待服务器连接...":
            self.server_label.config(text="等待服务器连接...", fg=FG_DIM)
        self.root.after(2000, self._poll_server_name)

    # ═══════════════════════════════════════════════════════════════
    #  Message handling
    # ═══════════════════════════════════════════════════════════════

    def get_recent_messages(self):
        return list(self._messages)

    def add_message(self, player_name: str, original: str, translated: str,
                    is_self: bool = False, detected_language: str = "",
                    timestamp: str = "", is_system: bool = False):
        self._messages.append((player_name, original, translated, is_self,
                               detected_language, timestamp, is_system))
        # Trim
        if len(self._messages) > self.cfg.max_messages:
            trimmed = len(self._messages) - self.cfg.max_messages
            self._messages = self._messages[-self.cfg.max_messages:]
            self._displayed_count = max(0, self._displayed_count - trimmed)
        # Sync display
        if not hasattr(self, '_sync_scheduled') or not self._sync_scheduled:
            self._sync_scheduled = True
            self.root.after_idle(self._do_sync_and_clear)

    def _do_sync_and_clear(self):
        self._sync_scheduled = False
        self._sync_display()

    def _sync_display(self):
        """Incrementally sync text widget from new messages."""
        try:
            self.text.configure(state=tk.NORMAL)
            new_total = len(self._messages)

            if new_total < self._displayed_count:
                self.text.delete("1.0", tk.END)
                self._displayed_count = 0

            insert_pos = tk.END
            for i in range(self._displayed_count, new_total):
                entry = self._messages[i]
                player, orig, trans, is_self, detected_lang, ts, is_sys = entry
                self._insert_one_at(insert_pos, player, orig, trans, is_self,
                                    detected_lang, ts, is_sys)

            self._displayed_count = new_total

            # Trim overflow
            max_lines = self.cfg.max_messages * 4  # each message is up to 4 lines
            total = int(self.text.index("end-1c").split(".")[0])
            if total > max_lines:
                self.text.delete("1.0", f"{total - max_lines + 1}.0")

            self.text.see(tk.END)
        finally:
            self.text.configure(state=tk.DISABLED)

    def _insert_one_at(self, pos, player: str, orig: str, trans: str,
                       is_self: bool, detected_lang: str = "",
                       timestamp: str = "", is_system: bool = False):
        """Render a single message in the new 3-line format:
        Line 1: [username]              timestamp
        Line 2:   translated_text (or system msg)
        Line 3:   original_text (gray, small)
        Line 4: ─── separator ───
        """
        prefix = "(You) " if is_self else ""

        if is_system:
            # System message: all gray, show translation if available
            tags = [
                ("system_text", f"[System]                              {timestamp}\n"),
                ("system_text", f"  {trans}\n"),
            ]
            if self.cfg.show_original_text and orig != trans:
                tags.append(("original", f"  {orig}\n"))
            tags.append(("separator", "─" * 70 + "\n"))
        else:
            # Build line 1: [prefix player] ... timestamp
            player_tag = "self_prefix" if is_self else "player"
            lang_tag = ""
            if self.cfg.show_language_label and detected_lang and not is_self:
                lang_tag = f"[{detected_lang}] "

            # Player name line with timestamp right-aligned
            player_text = f"{lang_tag}{prefix}[{player}]"
            # Pad with spaces to push timestamp to the right
            line1 = self._pad_line(player_text, timestamp, 60)

            tags = [
                (player_tag, line1 + "\n"),
            ]

            # Line 2: translation (indented 2 spaces)
            if trans != orig:
                ttag = "error" if trans.startswith("[") else "translation"
                tags.append((ttag, f"  {trans}\n"))
            else:
                tags.append(("translation", f"  {orig}\n"))

            # Line 3: original text (gray, smaller, indented)
            if self.cfg.show_original_text and orig != trans and not trans.startswith("["):
                tags.append(("original", f"  {orig}\n"))

            # Line 4: separator
            tags.append(("separator", "─" * 70 + "\n"))

        for tag, text in tags:
            if tag:
                self.text.insert(pos, text, tag)
            else:
                self.text.insert(pos, text)

    @staticmethod
    def _pad_line(left: str, right: str, width: int) -> str:
        """Pad left+right to approximate right-alignment using spaces."""
        if not right:
            return left
        total_space = max(2, width - len(left) - len(right))
        return left + (" " * total_space) + right

    def poll_messages(self):
        new_count = 0
        while True:
            try:
                item = self.queue.get_nowait()
                if isinstance(item, DisplayMessage):
                    self.add_message(
                        item.player_name, item.original_text,
                        item.translated_text, item.is_self,
                        item.detected_language, item.timestamp, item.is_system,
                    )
                    self.root.deiconify()
                    if not item.is_self:
                        new_count += 1
                elif isinstance(item, tuple) and len(item) >= 2:
                    # Legacy tuple support
                    msg, translated = item[0], item[1]
                    ts = getattr(msg, 'timestamp', '')
                    is_sys = getattr(msg, 'is_system', False)
                    self.add_message(msg.player_name, msg.text, translated, msg.is_self,
                                     "", ts, is_sys)
                    self.root.deiconify()
                    if not msg.is_self:
                        new_count += 1
            except Empty:
                break

        if new_count > 0:
            self._show_notice(f"翻译了 {new_count} 条消息", SELF_GREEN, "#1a2a1a")

        self._update_stats_display()
        self.root.after(250, self.poll_messages)

    def _show_notice(self, text: str, fg: str = ERROR_RED, bg: str = NOTICE_BG, duration_ms: int = 3000):
        if self._notice_after is not None:
            self.root.after_cancel(self._notice_after)
        self.notice_label.config(text=text, fg=fg, bg=bg)
        self.notice_label.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(2, 0), before=self.entry_row)
        self._notice_after = self.root.after(duration_ms, self.notice_label.pack_forget)

    # ═══════════════════════════════════════════════════════════════
    #  Input area — slide out from bottom
    # ═══════════════════════════════════════════════════════════════

    def _show_input(self):
        """Focus the always-visible input field."""
        self.send_entry.focus_set()

    def _hide_input(self):
        """Clear and defocus the input field."""
        self.send_entry.delete(0, tk.END)
        self._update_hotkey_hint()

    # ═══════════════════════════════════════════════════════════════
    #  Global hotkey (polling-based)
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _format_hotkey(raw: str) -> str:
        parts = [p.strip().title() for p in raw.strip().split("+")]
        return "+".join(parts)

    def _update_hotkey_hint(self):
        self.send_hint.config(
            text=f" {self._format_hotkey(self.cfg.send_hotkey)} 呼出 ",
            fg=FG_DIM,
        )

    def _parse_hotkey(self, hotkey_str: str) -> tuple[int, int]:
        parts = hotkey_str.lower().strip().split("+")
        mods = 0
        for p in parts[:-1]:
            p = p.strip()
            if p in ("shift", "shft"): mods |= MOD_SHIFT
            elif p in ("ctrl", "control"): mods |= MOD_CONTROL
            elif p in ("alt"): mods |= MOD_ALT
        key = parts[-1].strip()
        vk = ord(key.upper()) if len(key) == 1 else 0
        return mods, vk

    def _start_hotkey_poller(self):
        mods, vk = self._parse_hotkey(self.cfg.send_hotkey)
        if vk == 0:
            return

        log = get_logger()
        if log:
            log.info("HOT", f"全局热键: {self._format_hotkey(self.cfg.send_hotkey)}")

        self._hotkey_active = True

        def poller():
            mod_vks = []
            if mods & MOD_SHIFT: mod_vks.append(0x10)
            if mods & MOD_CONTROL: mod_vks.append(0x11)
            if mods & MOD_ALT: mod_vks.append(0x12)

            def held(vk_code): return ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000

            was_down = all(held(mv) for mv in mod_vks) and held(vk)
            while getattr(self, '_hotkey_active', False):
                mods_ok = all(held(mv) for mv in mod_vks) if mod_vks else True
                key_down = held(vk)
                combo = mods_ok and key_down

                if combo and not was_down:
                    self.root.after(0, self._focus_send_entry)
                was_down = combo
                time.sleep(0.05)

        t = threading.Thread(target=poller, daemon=True)
        t.start()

    def _stop_hotkey_poller(self):
        self._hotkey_active = False

    def _focus_send_entry(self):
        """Bring window to front and show input area."""
        try:
            self.root.deiconify()
            self.root.lift()
            hwnd = self.root.winfo_id()

            ctypes.windll.user32.AllowSetForegroundWindow(-1)
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)
            ctypes.windll.user32.BringWindowToTop(hwnd)

            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            fg_tid = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, 0)
            our_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            if fg_tid and fg_tid != our_tid:
                ctypes.windll.user32.AttachThreadInput(our_tid, fg_tid, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(our_tid, fg_tid, False)
            else:
                ctypes.windll.user32.SetForegroundWindow(hwnd)

            ctypes.windll.user32.SetActiveWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)
            self.root.focus_force()

            self.send_entry.focus_set()
            self._click_on_widget(self.send_entry)
            self.root.after(50, lambda: self._retry_focus())
            self.root.after(150, lambda: self._retry_focus())
        except Exception:
            pass

    def _retry_focus(self):
        try:
            if self.root.state() == "withdrawn":
                return
            self.send_entry.focus_set()
            self._click_on_widget(self.send_entry)
        except Exception:
            pass

    def update_send_hotkey(self, new_hotkey: str):
        self._stop_hotkey_poller()
        self.cfg.send_hotkey = new_hotkey
        self._update_hotkey_hint()
        self._start_hotkey_poller()
        # Update shortcuts bar
        shortcuts = [
            f"{self._format_hotkey(new_hotkey)} 呼出输入框",
            "Enter 翻译发送",
        ]
        self.shortcuts_label.config(text="  |  ".join(shortcuts))
        log = get_logger()
        if log:
            log.info("HOT", f"热键变更: {self._format_hotkey(new_hotkey)}")

    # ═══════════════════════════════════════════════════════════════
    #  Send chat message pipeline
    # ═══════════════════════════════════════════════════════════════

    def _on_send_enter(self, event):
        if self._sending:
            return "break"
        text = self.send_entry.get().strip()
        if not text:
            return "break"

        self._sending = True
        self._pending_chinese = text
        self.send_entry.delete(0, tk.END)
        self.send_entry.config(state=tk.DISABLED)
        self.send_hint.config(text=" 翻译中... ", fg=FG)

        import threading
        threading.Thread(target=self._do_translate, args=(text,), daemon=True).start()
        return "break"

    def _do_translate(self, chinese_text: str):
        from translator import translate_for_send
        try:
            english = translate_for_send(self.cfg, chinese_text)
        except Exception as e:
            self.root.after(0, lambda: self._on_translate_error(str(e)))
            return
        self.root.after(0, lambda: self._on_translate_done(chinese_text, english))

    def _on_translate_done(self, chinese: str, english: str):
        self.send_entry.delete(0, tk.END)
        self.send_hint.config(text=" 正在发送到游戏... ", fg="#dcdcaa")
        import threading
        threading.Thread(target=self._do_auto_send, args=(chinese, english), daemon=True).start()

    def _do_auto_send(self, chinese: str, english: str):
        from compose_sender import ComposeSender, SendResult
        sender = ComposeSender(self.cfg)

        if not sender.validate(chinese, english):
            self.root.after(0, lambda: self._on_send_done(
                SendResult.FAIL_TRANSLATION, chinese, english))
            return

        hide_done = threading.Event()
        self.root.after(0, lambda: (self.hide(), hide_done.set()))
        if not hide_done.wait(timeout=1.0):
            self.root.after(0, lambda: self._on_send_done(
                SendResult.FAIL_SEND, chinese, english))
            return
        time.sleep(0.25)

        result = sender.execute_send(english)
        self.root.after(0, self.show)
        self.root.after(0, lambda: self._on_send_done(result, chinese, english))

    def _on_send_done(self, result, chinese: str, english: str):
        from compose_sender import SendResult
        self._sending = False
        self.send_entry.config(state=tk.NORMAL)

        if result == SendResult.OK_CONFIRMED:
            self._insert_sent(chinese, english)
            self.send_hint.config(text=" 已发送并确认 ✓ ", fg=SELF_GREEN)
        elif result == SendResult.OK_UNCONFIRMED:
            self._insert_sent(chinese, english)
            self.send_hint.config(text=" 已发送（未确认） ", fg="#dcdcaa")
        elif result == SendResult.FAIL_TRANSLATION:
            self.send_entry.insert(0, english)
            self.send_entry.select_range(0, tk.END)
            self.send_hint.config(text=" 翻译无效，未发送 ", fg=ERROR_RED)
        elif result == SendResult.FAIL_SEND:
            self.send_entry.insert(0, english)
            self.send_entry.select_range(0, tk.END)
            self.send_hint.config(text=" 发送失败 ", fg=ERROR_RED)
        else:
            self.send_hint.config(text=" 未知状态 ", fg=FG_DIM)

        self._hide_input()

    def _on_translate_error(self, error: str):
        self._sending = False
        self.send_entry.config(state=tk.NORMAL)
        self.send_hint.config(text=" 翻译失败 ", fg=ERROR_RED)
        self._hide_input()
        self.add_message("System", "发送翻译失败", error, is_self=True)
        log = get_logger()
        if log:
            log.error("LLM", f"发送翻译失败: {error}")

    def _insert_sent(self, chinese: str, english: str):
        self._messages.append(("(Sent)", english, chinese, True, "", "", False))
        if len(self._messages) > self.cfg.max_messages:
            self._messages = self._messages[-self.cfg.max_messages:]
            self._displayed_count = max(0, self._displayed_count - 1)
        if not hasattr(self, '_sync_scheduled') or not self._sync_scheduled:
            self._sync_scheduled = True
            self.root.after_idle(self._do_sync_and_clear)

    def _click_on_widget(self, widget):
        try:
            self.root.update_idletasks()
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() // 2
            ctypes.windll.user32.SetCursorPos(x, y)
            time.sleep(0.02)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.02)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  Show / hide
    # ═══════════════════════════════════════════════════════════════

    def hide(self):
        self._stop_hotkey_poller()
        self._save_position()
        save_config(self.cfg)
        self.root.withdraw()

    def show(self):
        self.root.deiconify()
        self._acrylic_applied = False  # reset so acrylic re-applies after un-hide
        self.root.after(100, self._apply_acrylic)
        self._start_hotkey_poller()

    def toggle_visibility(self):
        if self.root.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def set_opacity(self, value: float):
        self.cfg.window_opacity = value
        # Opacity only applies if acrylic failed (alpha fallback)
        try:
            self.root.attributes("-alpha", value)
        except Exception:
            pass

    def set_font_size(self, size: int):
        self.cfg.font_size = size
        self.text.configure(font=("Microsoft YaHei", size))  # base font
        self.send_entry.configure(font=("Microsoft YaHei", size))
        self._setup_text_tags()

    def run(self):
        self.root.after(100, self.poll_messages)
        self.root.mainloop()
