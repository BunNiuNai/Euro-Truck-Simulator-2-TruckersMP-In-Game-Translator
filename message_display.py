"""
Message display engine — text widget, stats bar, rendering logic.
Extracted from overlay.py for modularity.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import AppConfig
from message_types import TranslationStats

BG = "#000000"
FG = "#cccccc"


class MessageDisplay:
    """Owns the text widget and stats bar for displaying translated messages."""

    def __init__(self, parent: tk.Widget, cfg: AppConfig, stats_ref: TranslationStats | dict | None = None):
        self.cfg = cfg
        self.stats_ref = stats_ref or {}
        self._messages: list[tuple[str, str, str, bool]] = []  # (player, orig, trans, is_self)
        self._displayed_count = 0
        self._sync_scheduled = False
        self._is_overlay: bool = False
        self._notice_after: str | None = None

        # Build text area
        self._build_text_widget(parent)
        self._build_stats_bar(parent)
        self._build_context_menu()

    # ── Text widget ──

    def _build_text_widget(self, parent: tk.Widget) -> None:
        text_frame = tk.Frame(parent, bg=BG)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=(0, 1))

        self.text = tk.Text(
            text_frame,
            font=("Microsoft YaHei", self.cfg.font_size),
            bg=BG, fg=FG,
            wrap=tk.WORD, state=tk.DISABLED,
            borderwidth=0, highlightthickness=0,
            padx=6, pady=4, insertbackground=FG,
        )
        vbar = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.text.configure(yscrollcommand=vbar.set)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y, before=self.text)

        self._grip_tag = "grip_marker"

        self._setup_color_tags()

    def _setup_color_tags(self) -> None:
        fs = self.cfg.font_size
        self.text.tag_configure("player", foreground="#569cd6",
                                font=("Microsoft YaHei", fs, "bold"))
        self.text.tag_configure("original", foreground=FG)
        self.text.tag_configure("arrow", foreground="#6a6a6a")
        self.text.tag_configure("translation", foreground="#dcdcaa")
        self.text.tag_configure("self_prefix", foreground="#4ec9b0")
        self.text.tag_configure("error", foreground="#f44747")
        self.text.tag_configure("baidu_fix", foreground="#f44747",
                                font=("Microsoft YaHei", fs, "bold"))
        self.text.tag_configure("sent_prefix", foreground="#4ec9b0",
                                font=("Microsoft YaHei", fs, "bold"))
        self.text.tag_configure("sent_arrow", foreground="#5a8a5a")
        self.text.tag_configure("separator", foreground="#aaaaaa",
                                font=("Microsoft YaHei", max(6, fs - 6)))
        self.text.tag_configure(self._grip_tag, foreground="#555555",
                                font=("Microsoft YaHei", max(6, fs - 6)))

    def _build_stats_bar(self, parent: tk.Widget) -> None:
        self.stats_frame = tk.Frame(parent, bg="#0f0f0f", height=28)
        self.stats_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.stats_frame.pack_propagate(False)

        def _make_stat(container: tk.Frame, label_text: str) -> tk.Label:
            f = tk.Frame(container, bg="#0f0f0f")
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

    def _build_context_menu(self) -> None:
        self.ctx_menu = tk.Menu(self.text, tearoff=0, bg="#222222", fg=FG)
        self.ctx_menu.add_command(label="Settings / 设置")
        self.ctx_menu.add_command(label="Switch Mode / 切换模式")
        self.ctx_menu.add_command(label="Check Updates / 检查更新")
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Hide / 隐藏")
        self.ctx_menu.add_command(label="Exit / 退出")

    def set_context_callbacks(
        self,
        settings_cb: callable | None = None,
        switch_mode_cb: callable | None = None,
        check_update_cb: callable | None = None,
        hide_cb: callable | None = None,
        exit_cb: callable | None = None,
    ) -> None:
        """Re-bind context menu commands to actual callbacks."""
        menu = self.ctx_menu
        menu.entryconfigure(0, command=settings_cb)
        menu.entryconfigure(1, command=switch_mode_cb)
        menu.entryconfigure(2, command=check_update_cb)
        menu.entryconfigure(4, command=hide_cb)
        menu.entryconfigure(5, command=exit_cb)

    # ── Message list management ──

    def add_message(self, player_name: str, original: str, translated: str, is_self: bool = False) -> None:
        self._messages.append((player_name, original, translated, is_self))
        if len(self._messages) > self.cfg.max_messages:
            trimmed = len(self._messages) - self.cfg.max_messages
            self._messages = self._messages[-self.cfg.max_messages:]
            self._displayed_count = max(0, self._displayed_count - trimmed)
        if not self._sync_scheduled:
            self._sync_scheduled = True
            self.text.after_idle(self._do_sync_and_clear)

    def insert_sent(self, chinese: str, english: str) -> None:
        """Display a sent message in the chat window."""
        self._messages.append(("(Sent)", english, chinese, True))
        if len(self._messages) > self.cfg.max_messages:
            self._messages = self._messages[-self.cfg.max_messages:]
            self._displayed_count = max(0, self._displayed_count - 1)
        if not self._sync_scheduled:
            self._sync_scheduled = True
            self.text.after_idle(self._do_sync_and_clear)

    def update_last_sys_msg(self, new_translated: str) -> None:
        """Update the translated text of the last message."""
        if self._messages:
            last = self._messages[-1]
            self._messages[-1] = (last[0], last[1], new_translated, last[3])
        self._displayed_count = 0
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        if self._is_overlay:
            self.text.insert(tk.END, " /", self._grip_tag)
        self.text.configure(state=tk.DISABLED)
        self._sync_display()

    # ── Rendering ──

    def _do_sync_and_clear(self) -> None:
        self._sync_scheduled = False
        self._sync_display()

    def _sync_display(self) -> None:
        """Incrementally sync the text widget with _messages."""
        self.text.configure(state=tk.NORMAL)
        new_total = len(self._messages)

        if new_total < self._displayed_count:
            self.text.delete("1.0", tk.END)
            self._displayed_count = 0
            if self._is_overlay:
                self.text.insert(tk.END, " /", self._grip_tag)

        insert_pos = "end-1c" if self._is_overlay else tk.END
        for i in range(self._displayed_count, new_total):
            player, orig, trans, is_self = self._messages[i]
            self._insert_one_at(insert_pos, player, orig, trans, is_self)

        self._displayed_count = new_total

        max_lines = self.cfg.max_messages
        total = int(self.text.index("end-1c").split(".")[0])
        if total > max_lines:
            self.text.delete("1.0", f"{total - max_lines + 1}.0")

        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    def _insert_one_at(self, pos: str, player: str, orig: str, trans: str, is_self: bool) -> None:
        prefix = "(You) " if is_self else ""
        tags: list[tuple[str | None, str]] = [
            ("player", f"{prefix}["),
        ]
        tags.append(("player" if not is_self else "self_prefix", f"{player}"))
        tags.append(("player", "] "))
        tags.append(("original", f"{orig}"))
        if trans != orig:
            tags.append(("arrow", " -> "))
            if trans.startswith("[百度优化]"):
                tag = "baidu_fix"
            elif trans.startswith("["):
                tag = "error"
            else:
                tag = "translation"
            tags.append((tag, trans))
        tags.append((None, "\n"))
        tags.append(("separator", "/" * 80 + "\n"))

        for tag, text in tags:
            if tag:
                self.text.insert(pos, text, tag)
            else:
                self.text.insert(pos, text)

    def show_notice(self, text: str, fg: str = "#f44747", bg: str = "#2a2a2a", duration_ms: int = 3000) -> None:
        """Show a notice label. The caller owns the label widget placement."""
        if not hasattr(self, 'notice_label') or self.notice_label is None:
            return
        if self._notice_after is not None:
            self.text.after_cancel(self._notice_after)
        self.notice_label.config(text=text, fg=fg, bg=bg)
        self.notice_label.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(2, 0))
        self._notice_after = self.text.after(duration_ms, self.notice_label.pack_forget)

    def set_notice_label(self, label: tk.Label) -> None:
        self.notice_label = label

    # ── Stats ──

    def update_stats(self) -> None:
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
        self._stat_self.config(text=str(stats.self_skipped))
        self._stat_saved.config(text=stats.savings_pct())

    # ── Font ──

    def set_font_size(self, size: int) -> None:
        self.cfg.font_size = size
        font = ("Microsoft YaHei", size)
        bold_font = ("Microsoft YaHei", size, "bold")
        small_font = ("Microsoft YaHei", max(6, size - 6))

        self.text.configure(font=font)
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
        self.text.tag_configure(self._grip_tag, font=small_font)
