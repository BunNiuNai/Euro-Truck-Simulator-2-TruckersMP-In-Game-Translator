"""
Translation display window - supports two modes:
  - "standalone": normal window with title bar, resizable
  - "overlay": borderless transparent overlay with optional click-through
"""
from __future__ import annotations

import ctypes
import os
import re
import threading
import time
import tkinter as tk
from datetime import datetime
from queue import Queue, Empty
from tkinter import ttk

from config import AppConfig, VERSION, save_config
from message_types import DisplayMessage, TranslationStats
from win32_constants import (
    GWL_EXSTYLE, GWLP_WNDPROC, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW,
    WM_HOTKEY, HOTKEY_SEND_ID,
    MOD_SHIFT, MOD_CONTROL, MOD_ALT,
    VK_SHIFT, VK_CONTROL, VK_ALT,
    SPECIAL_VK, KEY_NAME_MAP,
    POINT, mod_vk,
)

from logger import get_logger

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

BG = "#000000"
FG = "#cccccc"


class OverlayWindow:
    """Tkinter overlay window showing translated chat messages."""

    def __init__(self, cfg: AppConfig, message_queue: Queue, stats_ref: dict = None):
        self.cfg = cfg
        self.queue = message_queue
        self.stats_ref = stats_ref or {}
        self.root = tk.Tk()
        self.root.title(f"ETS2 聊天翻译器 {VERSION}")
        self.root.configure(bg=BG)
        self._messages = []
        self._displayed_count = 0  # how many messages are currently shown
        self._is_overlay = False
        self._edge_code = ""
        self._save_pos_after = None  # after_id for debounced position save
        self._ready = False  # suppress save during init
        self._setup_ui()
        self._apply_mode()
        self._restore_or_center()
        self._set_rounded_corners()
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.after(1000, lambda: setattr(self, "_ready", True))

        # Start global hotkey poller after window is ready
        self.root.after(500, self._start_hotkey_poller)

    def _setup_ui(self):
        # Outer container
        self.outer = tk.Frame(self.root, bg=BG, bd=0)
        self.outer.pack(fill=tk.BOTH, expand=True)

        # Title bar (only visible in overlay mode, used as drag handle)
        self.title_bar = tk.Frame(self.outer, bg="#181818", height=22, cursor="fleur")
        self.title_label = tk.Label(
            self.title_bar, text=f" ETS2 聊天翻译器 {VERSION}",
            bg="#181818", fg="#666666", font=("Microsoft YaHei", 9), anchor=tk.W
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.close_btn = tk.Label(
            self.title_bar, text="X ", bg="#181818", fg="#666666",
            font=("Microsoft YaHei", 10, "bold"), cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT)
        self.close_btn.bind("<Button-1>", lambda e: self.hide())

        # Overlay-mode mouse handlers for drag & resize (frame + title bar)
        for w in (self.outer, self.title_bar, self.title_label):
            w.bind("<Button-1>", self._on_mouse_down)
            w.bind("<B1-Motion>", self._on_mouse_move)
            w.bind("<Motion>", self._on_mouse_hover)
            w.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Pack BOTTOM elements FIRST to reserve their space

        # Stats bar — multi-label for mixed colors
        self.stats_frame = tk.Frame(self.outer, bg="#0f0f0f", height=28)
        self.stats_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.stats_frame.pack_propagate(False)

        def _make_stat(parent, label_text):
            """Create a (label, number) pair in a sub-frame."""
            f = tk.Frame(parent, bg="#0f0f0f")
            f.pack(side=tk.LEFT, padx=6)
            lb = tk.Label(f, text=label_text, bg="#0f0f0f", fg="#cccccc",
                          font=("Microsoft YaHei", 9))
            lb.pack(side=tk.LEFT)
            num = tk.Label(f, text="0", bg="#0f0f0f", fg="#f44747",
                           font=("Microsoft YaHei", 9, "bold"))
            num.pack(side=tk.LEFT)
            return num

        self._stat_translated = _make_stat(self.stats_frame, "已翻译: ")
        self._stat_cached = _make_stat(self.stats_frame, "缓存命中: ")
        self._stat_self = _make_stat(self.stats_frame, "跳过(自己): ")
        self._stat_saved = _make_stat(self.stats_frame, "节省: ")

        # Beijing time — bottom-right corner
        self._time_label = tk.Label(self.stats_frame, text="", bg="#0f0f0f", fg="#ffffff",
                                     font=("Microsoft YaHei", 9, "bold"), padx=8)
        self._time_label.pack(side=tk.RIGHT)
        self._update_clock()

        # Input area (packed second, auto-sizes to fit children)
        self.input_frame = tk.Frame(self.outer, bg=BG)
        self.input_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Notice label (hidden by default, shown above entry for translation events)
        self.notice_label = tk.Label(
            self.input_frame, text="", bg="#2a2a2a", fg="#f44747",
            font=("Microsoft YaHei", 10, "bold"), anchor=tk.CENTER, height=1
        )
        self._notice_after = None

        # Entry row
        self.entry_row = tk.Frame(self.input_frame, bg=BG, height=32)
        self.entry_row.pack(fill=tk.X, padx=4, pady=(1, 3))
        self.send_entry = tk.Entry(
            self.entry_row, font=("Microsoft YaHei", self.cfg.font_size),
            bg="#1a1a1a", fg=FG, insertbackground=FG,
            relief=tk.FLAT, borderwidth=0,
        )
        self.send_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        hotkey_display = self._format_hotkey(self.cfg.send_hotkey)
        self.send_hint = tk.Label(
            self.entry_row, text=f" {hotkey_display} 呼出 ", bg=BG, fg="#888888",
            font=("Microsoft YaHei", 9),
        )
        self.send_hint.pack(side=tk.RIGHT, padx=(4, 0))
        self.send_entry.bind("<Return>", self._on_send_enter)
        self.send_entry.bind("<Escape>", lambda e: (
            self.send_entry.delete(0, tk.END), self._update_hotkey_hint()
        ))
        self.send_entry.bind("<FocusIn>", lambda e: self.send_hint.config(text=" 输入中文 "))
        self.send_entry.bind("<FocusOut>", lambda e: self._update_hotkey_hint())

        # Countdown frame (shown during send countdown, hidden otherwise)
        self.countdown_frame = tk.Frame(self.input_frame, bg=BG, height=28)
        self.countdown_label = tk.Label(
            self.countdown_frame, text="", bg=BG, fg="#f44747",
            font=("Microsoft YaHei", 10),
        )
        self.countdown_label.pack(side=tk.LEFT, padx=6)
        self.countdown_cancel = tk.Label(
            self.countdown_frame, text="[ESC 取消发送]", bg=BG, fg="#f44747",
            font=("Microsoft YaHei", 9), cursor="hand2",
        )
        self.countdown_cancel.pack(side=tk.RIGHT, padx=6)
        self.countdown_cancel.bind("<Button-1>", lambda e: (
            self.send_entry.delete(0, tk.END), self._update_hotkey_hint()
        ))

        # Sending state
        self._sending = False
        self._pending_chinese = ""
        self._pending_english = ""

        # Text area (packed LAST — gets remaining space after bottom elements)
        text_frame = tk.Frame(self.outer, bg=BG)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

        self.text = tk.Text(
            text_frame,
            font=("Microsoft YaHei", self.cfg.font_size),
            bg=BG,
            fg=FG,
            wrap=tk.WORD,
            state=tk.DISABLED,
            borderwidth=0,
            highlightthickness=0,
            padx=6, pady=4,
            insertbackground=FG,
        )
        vbar = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=vbar.set)

        # Layout inside text_frame
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y, before=self.text)

        # Save position + reapply rounded corners on window resize
        self.root.bind("<Configure>", lambda e: (self._schedule_save_position(), self._set_rounded_corners()))

        # Resize grip triangle drawn in text widget corner
        self._grip_tag = "grip_marker"
        self.text.tag_configure(self._grip_tag, foreground="#555555",
                                font=("Microsoft YaHei", 10))

        # Text widget mouse handlers for drag & resize
        self.text.bind("<Button-1>", self._on_mouse_down)
        self.text.bind("<B1-Motion>", self._on_mouse_move)
        self.text.bind("<Motion>", self._on_mouse_hover)
        self.text.bind("<ButtonRelease-1>", self._on_mouse_up)

        # Color tags
        self.text.tag_configure("player", foreground="#569cd6",
                                font=("Microsoft YaHei", self.cfg.font_size, "bold"))
        self.text.tag_configure("original", foreground=FG)
        self.text.tag_configure("arrow", foreground="#6a6a6a")
        self.text.tag_configure("translation", foreground="#dcdcaa")
        self.text.tag_configure("self_prefix", foreground="#4ec9b0")
        self.text.tag_configure("error", foreground="#f44747")
        self.text.tag_configure("baidu_fix", foreground="#f44747",
                                font=("Microsoft YaHei", self.cfg.font_size, "bold"))
        self.text.tag_configure("sent_prefix", foreground="#4ec9b0",
                                font=("Microsoft YaHei", self.cfg.font_size, "bold"))
        self.text.tag_configure("sent_arrow", foreground="#5a8a5a")
        self.text.tag_configure("separator", foreground="#aaaaaa",
                                font=("Microsoft YaHei", 6))

        # Right-click menu
        self.ctx_menu = tk.Menu(self.root, tearoff=0, bg="#222222", fg=FG)
        self.ctx_menu.add_command(label="Settings / 设置", command=self._on_settings)
        self.ctx_menu.add_command(label="Switch Mode / 切换模式", command=self._toggle_mode)
        self.ctx_menu.add_command(label="Check Updates / 检查更新", command=self._on_check_update)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Hide / 隐藏", command=self.hide)
        self.ctx_menu.add_command(label="Exit / 退出", command=self._on_exit)
        self.text.bind("<Button-3>", lambda e: self.ctx_menu.tk_popup(e.x_root, e.y_root))

        # Callback stubs (set by main.py)
        self._settings_cb = None
        self._switch_mode_cb = None
        self._exit_cb = None
        self._check_update_cb = None

    def _restore_or_center(self):
        """Restore saved window position or center on screen."""
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if self.cfg.win_w > 0 and self.cfg.win_h > 0 and self.cfg.win_x >= 0 and self.cfg.win_y >= 0:
            # Clamp to visible screen area
            x = max(0, min(self.cfg.win_x, sw - 100))
            y = max(0, min(self.cfg.win_y, sh - 100))
            w = min(self.cfg.win_w, sw)
            h = min(self.cfg.win_h, sh)
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            w = self.cfg.win_w if self.cfg.win_w > 0 else 620
            h = self.cfg.win_h if self.cfg.win_h > 0 else 360
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _set_rounded_corners(self):
        """Apply rounded corners to the window via DWM (Win11) or SetWindowRgn (Win10/overlay)."""
        try:
            hwnd = self.root.winfo_id()
            if self.cfg.window_mode != "overlay":
                # Standard mode: try DWM (Win11 native rounded corners)
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                    ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), ctypes.sizeof(ctypes.c_int))
            # Overlay mode / Win10 fallback: SetWindowRgn
            if self.cfg.window_mode == "overlay":
                self.root.update_idletasks()
                w = self.root.winfo_width()
                h = self.root.winfo_height()
                if w > 1 and h > 1:
                    r = 16  # corner radius
                    hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
                    ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass

    def _save_position(self):
        """Save window position and size to config."""
        if self.root.state() == "withdrawn":
            return
        try:
            g = self.root.winfo_geometry()
            # winfo_geometry is more reliable: "WxH+X+Y"
            import re
            m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", g)
            if m:
                self.cfg.win_w = int(m.group(1))
                self.cfg.win_h = int(m.group(2))
                self.cfg.win_x = int(m.group(3))
                self.cfg.win_y = int(m.group(4))
        except (ValueError, IndexError, AttributeError):
            return

    def _schedule_save_position(self):
        """Debounced save: wait 1 second after last drag/resize before saving."""
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
        """Apply window mode settings without resetting window size."""
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.cfg.window_opacity)

        was_visible = self.root.state() != "withdrawn"
        if was_visible:
            self.root.withdraw()

        if self.cfg.window_mode == "overlay":
            self._is_overlay = True
            self.root.resizable(False, False)
            self.root.minsize(280, 250)
            self.root.overrideredirect(True)
            self.root.update_idletasks()  # ensure new hwnd after overrideredirect
            self.title_bar.pack(side=tk.TOP, fill=tk.X)
            ex = ctypes.windll.user32.GetWindowLongPtrW(self.root.winfo_id(), GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongPtrW(self.root.winfo_id(), GWL_EXSTYLE, ex | WS_EX_TOOLWINDOW)
            self._set_click_through(self.cfg.click_through)
        else:
            self._is_overlay = False
            self.root.resizable(True, True)
            self.root.minsize(280, 250)
            self.root.overrideredirect(False)
            self.root.update_idletasks()  # ensure new hwnd after overrideredirect
            self.title_bar.pack_forget()
            ex = ctypes.windll.user32.GetWindowLongPtrW(self.root.winfo_id(), GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongPtrW(self.root.winfo_id(), GWL_EXSTYLE, ex & ~WS_EX_TOOLWINDOW & ~WS_EX_TRANSPARENT)

        if was_visible:
            self.root.deiconify()
        self.root.after(100, self._set_rounded_corners)

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
        else:
            if self.cfg.window_mode == "overlay":
                self.cfg.window_mode = "standalone"
            else:
                self.cfg.window_mode = "overlay"
            self._apply_mode()

    def _on_settings(self):
        if self._settings_cb:
            self._settings_cb()

    def _on_exit(self):
        if self._exit_cb:
            self._exit_cb()

    def _on_check_update(self):
        if self._check_update_cb:
            self._check_update_cb()

    # ----- mouse handling for borderless resize & drag (overlay mode) -----
    BORDER = 8
    MIN_W, MIN_H = 280, 250

    CURSORS = {
        "n":  "size_ns",      "s":  "size_ns",
        "w":  "size_we",      "e":  "size_we",
        "nw": "size_nw_se",   "se": "size_nw_se",
        "ne": "size_ne_sw",   "sw": "size_ne_sw",
    }

    def _win_xy(self, event):
        """Convert event to window-relative coordinates."""
        return event.x_root - self.root.winfo_rootx(), event.y_root - self.root.winfo_rooty()

    def _edge(self, wx, wy):
        """Return 2-char edge code (n/s/w/e combos) or '' if not on edge."""
        w, h = self.root.winfo_width(), self.root.winfo_height()
        e = ""
        if wx <= self.BORDER: e += "w"
        elif wx >= w - self.BORDER: e += "e"
        if wy <= self.BORDER: e += "n"
        elif wy >= h - self.BORDER: e += "s"
        return e

    def _on_mouse_hover(self, event):
        if not self._is_overlay: return
        wx, wy = self._win_xy(event)
        edge = self._edge(wx, wy)
        c = self.CURSORS.get(edge, "")
        self.outer.configure(cursor=c)
        self.title_bar.configure(cursor=c if c else "fleur")

    def _on_mouse_down(self, event):
        if not self._is_overlay: return
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
        if not self._is_overlay: return
        dx = event.x_root - self._mx
        dy = event.y_root - self._my

        if self._edge_code:
            # Clear old window region before resize to avoid clipping artifacts
            try:
                ctypes.windll.user32.SetWindowRgn(self.root.winfo_id(), 0, True)
            except Exception:
                pass
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
            self.root.update_idletasks()
            self._set_rounded_corners()  # reapply rounded corners at new size
            self._schedule_save_position()
        else:
            x = self._start_x + event.x_root - self._mx
            y = self._start_y + event.y_root - self._my
            self.root.geometry(f"+{x}+{y}")
            self.root.update_idletasks()
            self._schedule_save_position()

    # ----- message handling -----
    def _update_last_sys_msg(self, new_translated: str):
        """Update the translated text of the last message — used for download progress."""
        if self._messages:
            last = self._messages[-1]
            self._messages[-1] = (last[0], last[1], new_translated, last[3])
        # Force redraw
        self._displayed_count = 0
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        if self._is_overlay:
            self.text.insert(tk.END, " ◢", self._grip_tag)
        self.text.configure(state=tk.DISABLED)
        self._sync_display()

    def get_recent_messages(self):
        """Return recent messages for the message log (settings tab)."""
        return list(self._messages)

    def add_message(self, player_name: str, original: str, translated: str, is_self: bool = False):
        self._messages.append((player_name, original, translated, is_self))
        # Write to message log file
        try:
            from logger import get_logger
            log = get_logger()
            if log:
                prefix = "(You) " if is_self else ""
                log.message_log(f"[{prefix}{player_name}] {original} → {translated}")
        except Exception:
            pass
        if len(self._messages) > self.cfg.max_messages:
            trimmed = len(self._messages) - self.cfg.max_messages
            self._messages = self._messages[-self.cfg.max_messages:]
            self._displayed_count = max(0, self._displayed_count - trimmed)
        # Schedule a display sync (debounced via after_idle)
        if not hasattr(self, '_sync_scheduled') or not self._sync_scheduled:
            self._sync_scheduled = True
            self.root.after_idle(self._do_sync_and_clear)

    def _do_sync_and_clear(self):
        self._sync_scheduled = False
        self._sync_display()

    def _sync_display(self):
        """Incrementally sync the text widget with _messages.
        Only inserts new messages since last sync; avoids full redraw.
        """
        self.text.configure(state=tk.NORMAL)
        new_total = len(self._messages)

        # Messages list was trimmed (rotated) — reset display
        if new_total < self._displayed_count:
            self.text.delete("1.0", tk.END)
            self._displayed_count = 0
            if self._is_overlay:
                self.text.insert(tk.END, " ◢", self._grip_tag)

        # Insert new messages before the grip marker (if any)
        insert_pos = "end-1c" if self._is_overlay else tk.END
        for i in range(self._displayed_count, new_total):
            player, orig, trans, is_self = self._messages[i]
            self._insert_one_at(insert_pos, player, orig, trans, is_self)

        self._displayed_count = new_total

        # Trim overflow lines from the top (2 lines per message: content + separator)
        max_lines = self.cfg.max_messages * 2
        total = int(self.text.index("end-1c").split(".")[0])
        if total > max_lines:
            self.text.delete("1.0", f"{total - max_lines + 1}.0")

        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    def _insert_one_at(self, pos, player: str, orig: str, trans: str, is_self: bool):
        """Insert a single message at the given position."""
        prefix = "(You) " if is_self else ""
        tags = []
        tags.append(("player", f"{prefix}["))
        tags.append(("player" if not is_self else "self_prefix", f"{player}"))
        tags.append(("player", "] "))
        tags.append(("original", f"{orig}"))
        if trans != orig:
            tags.append(("arrow", " → "))
            if trans.startswith("[百度优化]"):
                tag = "baidu_fix"
            elif trans.startswith("["):
                tag = "error"
            else:
                tag = "translation"
            tags.append((tag, trans))
        tags.append((None, "\n"))
        # White separator line under each message
        tags.append(("separator", "─" * 80 + "\n"))

        for tag, text in tags:
            if tag:
                self.text.insert(pos, text, tag)
            else:
                self.text.insert(pos, text)

    def poll_messages(self):
        new_count = 0
        baidu_count = 0
        while True:
            try:
                item = self.queue.get_nowait()
                if isinstance(item, DisplayMessage):
                    translated = item.translated_text
                    if item.baidu_fixed:
                        translated = f"[百度优化] {translated}"
                        baidu_count += 1
                    self.add_message(
                        item.player_name, item.original_text,
                        translated, item.is_self,
                    )
                    self.root.deiconify()
                    if not item.is_self:
                        new_count += 1
                elif isinstance(item, tuple) and len(item) >= 2:
                    # Legacy tuple support for backward compatibility
                    msg, translated = item[0], item[1]
                    baidu_fixed = len(item) >= 3 and item[2]
                    if baidu_fixed:
                        translated = f"[百度优化] {translated}"
                        baidu_count += 1
                    self.add_message(msg.player_name, msg.text, translated, msg.is_self)
                    self.root.deiconify()
                    if not msg.is_self:
                        new_count += 1
            except Empty:
                break

        if baidu_count > 0:
            self._show_notice(f"百度翻译优化了 {baidu_count} 条翻译", "#f44747")
        elif new_count > 0:
            self._show_notice(f"大模型翻译了 {new_count} 条消息", "#4ec9b0", "#1a2a1a")

        self._update_stats()
        self.root.after(250, self.poll_messages)

    def _show_notice(self, text: str, fg: str = "#f44747", bg: str = "#2a2a2a", duration_ms: int = 3000):
        """Show a notice above the input box that auto-hides after duration_ms."""
        if self._notice_after is not None:
            self.root.after_cancel(self._notice_after)
        self.notice_label.config(text=text, fg=fg, bg=bg)
        self.notice_label.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(2, 0), before=self.entry_row)
        self._notice_after = self.root.after(duration_ms, self.notice_label.pack_forget)

    def _update_clock(self):
        """Update Beijing time display every second."""
        from datetime import datetime, timezone, timedelta
        beijing = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
        self._time_label.config(text=beijing.strftime("北京时间 %H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _update_stats(self):
        if not self.stats_ref:
            return
        if isinstance(self.stats_ref, TranslationStats):
            stats = self.stats_ref
        else:
            # Legacy dict support
            stats = TranslationStats(
                translated=self.stats_ref.get("translated", 0),
                cached=self.stats_ref.get("cached", 0),
                self_skipped=self.stats_ref.get("self", 0),
            )
        self._stat_translated.config(text=str(stats.translated))
        self._stat_cached.config(text=str(stats.cached))
        self._stat_self.config(text=str(stats.self_skipped))
        self._stat_saved.config(text=stats.savings_pct())

    # ----- global hotkey (polling-based, no WNDPROC hook needed) -----
    def _format_hotkey(self, raw: str) -> str:
        parts = [p.strip().title() for p in raw.strip().split("+")]
        return "+".join(parts)

    def _update_hotkey_hint(self):
        self.send_hint.config(
            text=f" {self._format_hotkey(self.cfg.send_hotkey)} 呼出 ",
            fg="#888888",
        )

    def _parse_hotkey(self, hotkey_str: str) -> tuple[int, int]:
        """Parse 'shift+y' into (mods_bitmask, virtual_key_code)."""
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
        """Background thread: polls GetAsyncKeyState for the hotkey combo."""
        mods, vk = self._parse_hotkey(self.cfg.send_hotkey)
        if vk == 0:
            return

        log = get_logger()
        if log:
            log.info("HOT", f"全局热键: {self._format_hotkey(self.cfg.send_hotkey)}")

        import threading
        self._hotkey_active = True

        def poller():
            # Map modifier flags to VK codes for GetAsyncKeyState
            mod_vks = []
            if mods & MOD_SHIFT: mod_vks.append(0x10)   # VK_SHIFT
            if mods & MOD_CONTROL: mod_vks.append(0x11)  # VK_CONTROL
            if mods & MOD_ALT: mod_vks.append(0x12)      # VK_MENU

            # High bit = key currently held down
            def held(vk_code): return ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000

            was_down = all(held(mv) for mv in mod_vks) and held(vk)
            while getattr(self, '_hotkey_active', False):
                # All required modifiers must be held
                mods_ok = all(held(mv) for mv in mod_vks) if mod_vks else True
                key_down = held(vk)
                combo = mods_ok and key_down

                if combo and not was_down:
                    # Edge-triggered: fire on key-down transition
                    self.root.after(0, self._focus_send_entry)
                was_down = combo
                threading.Event().wait(0.05)  # 50ms poll interval

        t = threading.Thread(target=poller, daemon=True)
        t.start()

    def _stop_hotkey_poller(self):
        self._hotkey_active = False

    def _focus_send_entry(self):
        """Bring window to front and set keyboard focus to the send entry.
        Uses multiple Windows API tricks to work around focus-stealing prevention."""
        try:
            self.root.deiconify()
            self.root.lift()
            hwnd = self.root.winfo_id()

            # Trick 1: AllowSetForegroundWindow — grant ourselves permission
            ctypes.windll.user32.AllowSetForegroundWindow(-1)

            # Trick 2: Simulate Alt key to trigger foreground permission
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)       # VK_MENU down
            ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)  # VK_MENU up

            # Trick 3: BringWindowToTop
            ctypes.windll.user32.BringWindowToTop(hwnd)

            # Trick 4: AttachThreadInput + SetForegroundWindow
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            fg_tid = ctypes.windll.user32.GetWindowThreadProcessId(fg_hwnd, 0)
            our_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            if fg_tid and fg_tid != our_tid:
                ctypes.windll.user32.AttachThreadInput(our_tid, fg_tid, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(our_tid, fg_tid, False)
            else:
                ctypes.windll.user32.SetForegroundWindow(hwnd)

            # Trick 5: SetActiveWindow + SetFocus
            ctypes.windll.user32.SetActiveWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)

            # Tkinter-level focus
            self.root.focus_force()
            self.send_entry.focus_set()

            # Simulate mouse click on the entry for reliability
            self._click_on_widget(self.send_entry)

            # Retry focus after paint completes (multiple attempts)
            self.root.after(50, lambda: self._retry_focus())
            self.root.after(150, lambda: self._retry_focus())
        except Exception:
            pass

    def _retry_focus(self):
        """Retry setting focus to the entry widget."""
        try:
            if self.root.state() == "withdrawn":
                return
            self.send_entry.focus_set()
            self._click_on_widget(self.send_entry)
        except Exception:
            pass

    def update_send_hotkey(self, new_hotkey: str):
        """Called when user changes the hotkey in settings."""
        self._stop_hotkey_poller()
        self.cfg.send_hotkey = new_hotkey
        self._update_hotkey_hint()
        self._start_hotkey_poller()
        log = get_logger()
        if log:
            log.info("HOT", f"热键变更: {self._format_hotkey(new_hotkey)}")

    # ----- send chat message -----
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
        self.send_hint.config(text=" 翻译中... ", fg="#cccccc")

        import threading
        threading.Thread(target=self._do_translate, args=(text,), daemon=True).start()
        return "break"

    def _do_translate(self, chinese_text: str):
        from translator import translate_to_english

        try:
            english = translate_to_english(self.cfg, chinese_text)
        except Exception as e:
            self.root.after(0, lambda: self._on_translate_error(str(e)))
            return

        self.root.after(0, lambda: self._on_translate_done(chinese_text, english))

    def _on_translate_done(self, chinese: str, english: str):
        """Translation finished — start auto-send on background thread."""
        self.send_entry.delete(0, tk.END)
        self.send_hint.config(text=" 正在发送到游戏... ", fg="#dcdcaa")
        import threading
        threading.Thread(target=self._do_auto_send, args=(chinese, english), daemon=True).start()

    def _do_auto_send(self, chinese: str, english: str):
        """Background thread: validate → hide overlay → send → confirm → restore."""
        from compose_sender import ComposeSender, SendResult

        sender = ComposeSender(self.cfg)

        # Step 1: Validate translation
        if not sender.validate(chinese, english):
            self.root.after(0, lambda: self._on_send_done(
                SendResult.FAIL_TRANSLATION, chinese, english))
            return

        # Step 2: Hide overlay on main thread, wait for effect
        hide_done = threading.Event()
        self.root.after(0, lambda: (self.hide(), hide_done.set()))
        if not hide_done.wait(timeout=1.0):
            self.root.after(0, lambda: self._on_send_done(
                SendResult.FAIL_SEND, chinese, english))
            return
        time.sleep(0.25)

        # Step 3: Execute send + confirmation (blocks up to ~2.8s)
        result = sender.execute_send(english)

        # Step 4: Restore overlay on main thread
        self.root.after(0, self.show)

        # Step 5: Report result to UI
        self.root.after(0, lambda: self._on_send_done(result, chinese, english))

    def _on_send_done(self, result, chinese: str, english: str):
        """Main-thread callback: display result status in UI."""
        from compose_sender import SendResult

        self._sending = False
        self.send_entry.config(state=tk.NORMAL)

        if result == SendResult.OK_CONFIRMED:
            self._insert_sent(chinese, english)
            self.send_hint.config(text=" 已发送并确认 ✓ ", fg="#4ec9b0")
        elif result == SendResult.OK_UNCONFIRMED:
            self._insert_sent(chinese, english)
            self.send_hint.config(text=" 已发送（未确认） ", fg="#dcdcaa")
        elif result == SendResult.FAIL_TRANSLATION:
            self.send_entry.insert(0, english)
            self.send_entry.select_range(0, tk.END)
            self.send_hint.config(text=" 翻译无效，未发送 ", fg="#f44747")
        elif result == SendResult.FAIL_SEND:
            self.send_entry.insert(0, english)
            self.send_entry.select_range(0, tk.END)
            self.send_hint.config(text=" 发送失败 ", fg="#f44747")
        else:
            self.send_hint.config(text=" 未知状态 ", fg="#888888")

        # Auto-clear entry after 5 seconds
        self.root.after(5000, lambda: (
            self.send_entry.delete(0, tk.END),
            self._update_hotkey_hint()
        ))

    def _on_translate_error(self, error: str):
        self._sending = False
        self.send_entry.config(state=tk.NORMAL)
        self.send_hint.config(text=" 翻译失败 ", fg="#f44747")
        self.root.after(5000, lambda: self._update_hotkey_hint())
        self.add_message("System", "发送翻译失败", error, is_self=True)
        log = get_logger()
        if log:
            log.error("LLM", f"发送翻译失败: {error}")

    # ----- countdown frame (kept for layout, hidden by default) -----
    def _show_countdown(self):
        self.countdown_frame.pack(fill=tk.X, padx=4, pady=(0, 3))

    def _hide_countdown(self):
        self.countdown_frame.pack_forget()

    def _insert_sent(self, chinese: str, english: str):
        """Display a sent message in the chat window."""
        self._messages.append(("(Sent)", english, chinese, True))
        if len(self._messages) > self.cfg.max_messages:
            self._messages = self._messages[-self.cfg.max_messages:]
            self._displayed_count = max(0, self._displayed_count - 1)
        if not hasattr(self, '_sync_scheduled') or not self._sync_scheduled:
            self._sync_scheduled = True
            self.root.after_idle(self._do_sync_and_clear)

    def _click_on_widget(self, widget):
        """Move cursor to widget center and simulate a mouse click."""
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

    def hide(self):
        self._stop_hotkey_poller()
        self._save_position()
        save_config(self.cfg)
        self.root.withdraw()

    def show(self):
        self.root.deiconify()
        self._start_hotkey_poller()

    def toggle_visibility(self):
        if self.root.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def set_opacity(self, value: float):
        self.cfg.window_opacity = value
        self.root.attributes("-alpha", value)

    def set_font_size(self, size: int):
        """Update font size on all display widgets immediately."""
        self.cfg.font_size = size
        font = ("Microsoft YaHei", size)
        bold_font = ("Microsoft YaHei", size, "bold")
        small_font = ("Microsoft YaHei", max(6, size - 6))

        self.text.configure(font=font)
        self.send_entry.configure(font=font)

        self.text.tag_configure("player", font=bold_font)
        self.text.tag_configure("original", font=font)
        self.text.tag_configure("arrow", font=font)
        self.text.tag_configure("translation", font=font)
        self.text.tag_configure("self_prefix", font=font)
        self.text.tag_configure("error", font=font)
        self.text.tag_configure("baidu_fix", font=bold_font)
        self.text.tag_configure("sent_prefix", font=bold_font)
        self.text.tag_configure("sent_arrow", font=font)
        self.text.tag_configure("separator", font=small_font)
        self.text.tag_configure("grip_marker", font=small_font)

    def run(self):
        self.root.after(100, self.poll_messages)
        self.root.mainloop()
