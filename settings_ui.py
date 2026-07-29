"""
Settings UI for ETS2 Chat Translator.
Main-detail layout: left Provider list, right edit panel.
Uses Tkinter + ttk with VS Code dark theme.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from config import AppConfig, save_config
from provider_presets import (
    get_preset, get_presets_by_category,
    PROVIDER_ICONS, CATEGORIES, CATEGORY_LABELS,
    ProviderPreset,
)
from model_fetcher import fetch_models, test_connectivity


# ── VS Code dark theme colors ──
class Theme:
    PAGE_BG = "#1e1e1e"
    CARD_BG = "#2d2d30"
    CARD_BORDER = "#3e3e42"
    TEXT = "#cccccc"
    TEXT_SEC = "#858585"
    ACCENT = "#007acc"
    ACCENT_HOVER = "#1a8ad4"
    GREEN = "#4ec9b0"
    RED = "#f44747"
    YELLOW = "#cca700"
    INPUT_BG = "#252526"
    SEP = "#3e3e42"


class ProviderEditPanel(tk.Frame):
    """Right-side panel for editing a single provider."""

    def __init__(self, parent: tk.Widget, on_save: Callable, on_delete: Callable,
                 on_test: Callable, on_fetch_models: Callable):
        super().__init__(parent, bg=Theme.PAGE_BG)
        self._on_save = on_save
        self._on_delete = on_delete
        self._on_test = on_test
        self._on_fetch_models = on_fetch_models
        self._provider_index: int = -1
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        # ── Preset info bar ──
        self._preset_frame = tk.Frame(self, bg=Theme.CARD_BG,
                                       highlightbackground=Theme.CARD_BORDER,
                                       highlightthickness=1)
        self._preset_frame.grid(row=0, column=0, columnspan=2, sticky="ew",
                                padx=12, pady=(12, 4))
        self._preset_label = tk.Label(self._preset_frame, text="",
                                       bg=Theme.CARD_BG, fg=Theme.TEXT_SEC,
                                       font=("Microsoft YaHei", 9))
        self._preset_label.pack(side=tk.LEFT, padx=10, pady=4)

        self._clear_preset_btn = tk.Label(self._preset_frame, text="✕",
                                           bg=Theme.CARD_BG, fg=Theme.TEXT_SEC,
                                           font=("Microsoft YaHei", 9),
                                           cursor="hand2")
        self._clear_preset_btn.pack(side=tk.RIGHT, padx=10, pady=4)
        self._clear_preset_btn.bind("<Button-1>", lambda e: self._clear_preset())
        self._clear_preset_btn.bind("<Enter>",
            lambda e: self._clear_preset_btn.configure(fg=Theme.RED))
        self._clear_preset_btn.bind("<Leave>",
            lambda e: self._clear_preset_btn.configure(fg=Theme.TEXT_SEC))

        # ── Fields ──
        self._fields: dict[str, tk.Widget] = {}
        self._row = 1

        self._add_field("Label / 名称", "label_entry", show=None)
        self._add_field("Endpoint / 地址", "endpoint_entry", show=None)
        self._add_field("API Key / 密钥", "key_entry", show="*")

        # Model row with fetch button
        self._add_label("Model / 模型", self._row)
        model_frame = tk.Frame(self, bg=Theme.PAGE_BG)
        model_frame.grid(row=self._row, column=1, sticky="ew", padx=(0, 12), pady=3)
        self._model_entry = tk.Entry(model_frame, bg=Theme.INPUT_BG,
                                      fg=Theme.TEXT, insertbackground=Theme.TEXT,
                                      relief="solid", font=("Consolas", 10))
        self._model_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._fetch_btn = tk.Label(model_frame, text="📥", bg=Theme.PAGE_BG,
                                    fg=Theme.ACCENT, font=("Microsoft YaHei", 11),
                                    cursor="hand2", padx=4)
        self._fetch_btn.pack(side=tk.RIGHT)
        self._fetch_btn.bind("<Button-1>",
            lambda e: self._on_fetch_models(self._provider_index))
        self._fetch_btn.bind("<Enter>",
            lambda e: self._fetch_btn.configure(fg=Theme.ACCENT_HOVER))
        self._fetch_btn.bind("<Leave>",
            lambda e: self._fetch_btn.configure(fg=Theme.ACCENT))
        self._fields["model_entry"] = self._model_entry
        self._row += 1

        self._add_field("Weight / 权重", "weight_entry", show=None, default="100")
        self._add_field("Timeout / 超时(秒)", "timeout_entry", show=None, default="8")

        # ── Action buttons ──
        btn_frame = tk.Frame(self, bg=Theme.PAGE_BG)
        btn_frame.grid(row=self._row, column=0, columnspan=2, sticky="ew",
                       padx=12, pady=(16, 8))
        self._row += 1

        self._test_btn = tk.Label(btn_frame, text="🔍 测试连通",
                                   bg=Theme.CARD_BG, fg=Theme.ACCENT,
                                   font=("Microsoft YaHei", 10),
                                   padx=16, pady=4, cursor="hand2",
                                   highlightbackground=Theme.CARD_BORDER,
                                   highlightthickness=1)
        self._test_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._test_btn.bind("<Button-1>",
            lambda e: self._on_test(self._provider_index))
        self._test_btn.bind("<Enter>",
            lambda e: self._test_btn.configure(fg=Theme.ACCENT_HOVER))
        self._test_btn.bind("<Leave>",
            lambda e: self._test_btn.configure(fg=Theme.ACCENT))

        self._test_status = tk.Label(btn_frame, text="", bg=Theme.PAGE_BG,
                                      fg=Theme.TEXT_SEC,
                                      font=("Microsoft YaHei", 9))
        self._test_status.pack(side=tk.LEFT, padx=4)

        # Save / Delete buttons
        save_btn = tk.Label(btn_frame, text="💾 保存", bg=Theme.CARD_BG,
                            fg=Theme.GREEN, font=("Microsoft YaHei", 10),
                            padx=16, pady=4, cursor="hand2",
                            highlightbackground=Theme.CARD_BORDER,
                            highlightthickness=1)
        save_btn.pack(side=tk.RIGHT, padx=(4, 0))
        save_btn.bind("<Button-1>", lambda e: self._on_save())

        del_btn = tk.Label(btn_frame, text="🗑 删除", bg=Theme.CARD_BG,
                           fg=Theme.RED, font=("Microsoft YaHei", 10),
                           padx=16, pady=4, cursor="hand2",
                           highlightbackground=Theme.CARD_BORDER,
                           highlightthickness=1)
        del_btn.pack(side=tk.RIGHT, padx=(4, 0))
        del_btn.bind("<Button-1>",
            lambda e: self._on_delete(self._provider_index))

    def _add_label(self, text: str, row: int):
        lbl = tk.Label(self, text=text, bg=Theme.PAGE_BG, fg=Theme.TEXT_SEC,
                       font=("Microsoft YaHei", 9), anchor=tk.W)
        lbl.grid(row=row, column=0, sticky=tk.W, padx=(16, 8), pady=3)

    def _add_field(self, text: str, key: str, show: str | None = None,
                   default: str = ""):
        self._add_label(text, self._row)
        entry = tk.Entry(self, bg=Theme.INPUT_BG, fg=Theme.TEXT,
                        insertbackground=Theme.TEXT, relief="solid",
                        font=("Consolas", 10), show=show or "")
        entry.grid(row=self._row, column=1, sticky=tk.EW, padx=(0, 12), pady=3)
        if default:
            entry.insert(0, default)
        self._fields[key] = entry
        self._row += 1

    def _clear_preset(self):
        for entry in self._fields.values():
            if isinstance(entry, tk.Entry):
                entry.delete(0, tk.END)
        self._preset_label.config(text="✏️ 手动输入", fg=Theme.TEXT_SEC)

    def load_provider(self, index: int, provider: dict):
        self._provider_index = index
        self._fields["label_entry"].delete(0, tk.END)
        self._fields["label_entry"].insert(0, provider.get("label", ""))
        self._fields["endpoint_entry"].delete(0, tk.END)
        self._fields["endpoint_entry"].insert(0, provider.get("endpoint", ""))
        self._fields["key_entry"].delete(0, tk.END)
        self._fields["key_entry"].insert(0, provider.get("api_key", ""))
        self._model_entry.delete(0, tk.END)
        self._model_entry.insert(0, provider.get("model", ""))
        self._fields["weight_entry"].delete(0, tk.END)
        self._fields["weight_entry"].insert(0, str(provider.get("weight", 100)))
        self._fields["timeout_entry"].delete(0, tk.END)
        self._fields["timeout_entry"].insert(0, str(provider.get("timeout", 8)))

        preset_id = provider.get("preset_id", "")
        if preset_id:
            preset = get_preset(preset_id)
            if preset:
                self._preset_label.config(
                    text=f"📦 预设: {preset.name}", fg=Theme.ACCENT)
            else:
                self._preset_label.config(
                    text=f"📦 预设: {preset_id}", fg=Theme.TEXT_SEC)
        else:
            self._preset_label.config(text="✏️ 手动输入", fg=Theme.TEXT_SEC)

    def load_from_preset(self, preset: ProviderPreset):
        data = preset.to_provider_dict()
        self.load_provider(-1, data)
        self._preset_label.config(text=f"📦 预设: {preset.name}", fg=Theme.ACCENT)

    def gather_provider(self, index: int) -> dict:
        try:
            weight = int(self._fields["weight_entry"].get().strip() or "100")
        except ValueError:
            weight = 100
        try:
            timeout = int(self._fields["timeout_entry"].get().strip() or "8")
        except ValueError:
            timeout = 8
        return {
            "id": "",
            "label": self._fields["label_entry"].get().strip(),
            "endpoint": self._fields["endpoint_entry"].get().strip(),
            "api_key": self._fields["key_entry"].get().strip(),
            "model": self._model_entry.get().strip(),
            "enabled": True,
            "preset_id": "",
            "icon": "",
            "api_format": "openai",
            "weight": weight,
            "extra_headers": {},
            "extra_body": {},
            "timeout": timeout,
        }

    def set_test_status(self, text: str, ok: bool | None = None):
        if ok is True:
            self._test_status.config(text=text, fg=Theme.GREEN)
        elif ok is False:
            self._test_status.config(text=text, fg=Theme.RED)
        else:
            self._test_status.config(text=text, fg=Theme.TEXT_SEC)

    def clear(self):
        self._provider_index = -1
        for entry in self._fields.values():
            if isinstance(entry, tk.Entry):
                entry.delete(0, tk.END)
        self._preset_label.config(text="", fg=Theme.TEXT_SEC)
        self._test_status.config(text="")


class PresetSelectorDialog:
    """Modal dialog for selecting a provider preset."""

    def __init__(self, parent: tk.Toplevel):
        self.result: ProviderPreset | None = None
        self._custom_selected: bool = False

        self.top = tk.Toplevel(parent)
        self.top.title("添加 Provider — 选择预设")
        self.top.geometry("560x480")
        self.top.minsize(420, 340)
        self.top.resizable(True, True)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.configure(bg=Theme.PAGE_BG)
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._build()
        self.top.wait_window()

    def _build(self):
        # ── Search bar ──
        search_frame = tk.Frame(self.top, bg=Theme.PAGE_BG)
        search_frame.pack(fill=tk.X, padx=12, pady=(12, 8))
        search_icon = tk.Label(search_frame, text="🔍", bg=Theme.PAGE_BG,
                               fg=Theme.TEXT_SEC, font=("Microsoft YaHei", 11))
        search_icon.pack(side=tk.LEFT, padx=(0, 4))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._apply_filter())
        search_entry = tk.Entry(search_frame, textvariable=self._search_var,
                                bg=Theme.INPUT_BG, fg=Theme.TEXT,
                                insertbackground=Theme.TEXT,
                                relief="solid", font=("Microsoft YaHei", 10))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.focus_set()

        # ── Scrollable grid ──
        canvas_frame = tk.Frame(self.top, bg=Theme.PAGE_BG)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self._canvas = tk.Canvas(canvas_frame, bg=Theme.PAGE_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                  command=self._canvas.yview)
        self._scroll_frame = tk.Frame(self._canvas, bg=Theme.PAGE_BG)
        self._scroll_frame.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.top.bind("<Destroy>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        # ── Build preset cards by category ──
        self._preset_cards: list[tuple[tk.Frame, ProviderPreset]] = []
        by_category = get_presets_by_category()

        for cat_id, cat_label in CATEGORIES:
            presets_in_cat = by_category.get(cat_id, [])
            if not presets_in_cat:
                continue
            header = tk.Label(self._scroll_frame, text=cat_label,
                              bg=Theme.PAGE_BG, fg=Theme.TEXT_SEC,
                              font=("Microsoft YaHei", 10, "bold"))
            header.pack(fill=tk.X, pady=(12, 4))

            for i, preset in enumerate(presets_in_cat):
                if i % 2 == 0:
                    row_frame = tk.Frame(self._scroll_frame, bg=Theme.PAGE_BG)
                    row_frame.pack(fill=tk.X, pady=2)
                card = self._make_card(row_frame, preset)
                card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                self._preset_cards.append((card, preset))

        # ── Custom entry ──
        sep = tk.Frame(self._scroll_frame, height=1, bg=Theme.SEP)
        sep.pack(fill=tk.X, pady=(12, 4))
        custom_card = self._make_custom_card(self._scroll_frame)
        custom_card.pack(fill=tk.X, pady=2)

        # ── Bottom buttons ──
        btn_frame = tk.Frame(self.top, bg=Theme.PAGE_BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(8, 12))

        cancel_btn = tk.Label(btn_frame, text="取消", bg=Theme.CARD_BG,
                              fg=Theme.TEXT, font=("Microsoft YaHei", 10),
                              padx=20, pady=4, cursor="hand2",
                              highlightbackground=Theme.CARD_BORDER,
                              highlightthickness=1)
        cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))
        cancel_btn.bind("<Button-1>", lambda e: self._on_cancel())

    def _make_card(self, parent: tk.Frame, preset: ProviderPreset) -> tk.Frame:
        card = tk.Frame(parent, bg=Theme.CARD_BG,
                       highlightbackground=Theme.CARD_BORDER,
                       highlightthickness=1, padx=8, pady=6)
        icon_text = PROVIDER_ICONS.get(preset.icon, "🔗")
        header = tk.Frame(card, bg=Theme.CARD_BG)
        header.pack(fill=tk.X)
        tk.Label(header, text=icon_text, bg=Theme.CARD_BG,
                font=("Segoe UI Emoji", 14)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(header, text=preset.name, bg=Theme.CARD_BG,
                fg=Theme.TEXT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)
        if preset.description:
            tk.Label(card, text=preset.description, bg=Theme.CARD_BG,
                    fg=Theme.TEXT_SEC, font=("Microsoft YaHei", 8),
                    anchor=tk.W, justify=tk.LEFT, wraplength=220).pack(
                    fill=tk.X, pady=(2, 0))

        def on_enter(e, c=card):
            c.configure(bg="#3c3c40", highlightbackground=Theme.ACCENT)
            for ch in c.winfo_children():
                ch.configure(bg="#3c3c40")
                for gc in ch.winfo_children():
                    try: gc.configure(bg="#3c3c40")
                    except tk.TclError: pass

        def on_leave(e, c=card):
            c.configure(bg=Theme.CARD_BG, highlightbackground=Theme.CARD_BORDER)
            for ch in c.winfo_children():
                ch.configure(bg=Theme.CARD_BG)
                for gc in ch.winfo_children():
                    try: gc.configure(bg=Theme.CARD_BG)
                    except tk.TclError: pass

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        for child in card.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)
            for gc in child.winfo_children():
                gc.bind("<Enter>", on_enter)
                gc.bind("<Leave>", on_leave)

        def select(e=None, p=preset):
            self.result = p
            self.top.destroy()

        card.bind("<Button-1>", select)
        for child in card.winfo_children():
            child.bind("<Button-1>", select)
            for gc in child.winfo_children():
                gc.bind("<Button-1>", select)

        return card

    def _make_custom_card(self, parent: tk.Frame) -> tk.Frame:
        card = tk.Frame(parent, bg=Theme.CARD_BG,
                       highlightbackground=Theme.CARD_BORDER,
                       highlightthickness=1, padx=8, pady=6)
        header = tk.Frame(card, bg=Theme.CARD_BG)
        header.pack(fill=tk.X)
        tk.Label(header, text="✏️", bg=Theme.CARD_BG,
                font=("Segoe UI Emoji", 14)).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(header, text="手动输入", bg=Theme.CARD_BG,
                fg=Theme.TEXT, font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(card, text="不匹配任何预设，手动填写所有字段",
                bg=Theme.CARD_BG, fg=Theme.TEXT_SEC,
                font=("Microsoft YaHei", 8)).pack(fill=tk.X, pady=(2, 0))

        def on_enter(e, c=card):
            c.configure(bg="#3c3c40", highlightbackground=Theme.ACCENT_HOVER)
        def on_leave(e, c=card):
            c.configure(bg=Theme.CARD_BG, highlightbackground=Theme.CARD_BORDER)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        for child in card.winfo_children():
            child.bind("<Enter>", on_enter)
            child.bind("<Leave>", on_leave)

        def select(e=None):
            self._custom_selected = True
            self.top.destroy()

        card.bind("<Button-1>", select)
        for child in card.winfo_children():
            child.bind("<Button-1>", select)
            for gc in child.winfo_children():
                gc.bind("<Button-1>", select)

        return card

    def _apply_filter(self):
        query = self._search_var.get().strip().lower()
        for card, preset in self._preset_cards:
            name = preset.name.lower()
            desc = preset.description.lower()
            if not query or query in name or query in desc:
                card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
            else:
                card.pack_forget()

    def _on_cancel(self):
        self.result = None
        self.top.destroy()


class ProviderListPanel(tk.Frame):
    """Left-side panel with scrollable provider list and add button."""

    def __init__(self, parent: tk.Widget, on_select: Callable[[int], None]):
        super().__init__(parent, bg=Theme.CARD_BG)
        self._on_select = on_select
        self._providers: list[dict] = []
        self._selected_index: int = -1
        self._item_frames: list[tk.Frame] = []
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        title = tk.Label(self, text="📋 Provider 列表", bg=Theme.CARD_BG,
                        fg=Theme.TEXT, font=("Microsoft YaHei", 11, "bold"))
        title.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        canvas_frame = tk.Frame(self, bg=Theme.CARD_BG)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)

        self._canvas = tk.Canvas(canvas_frame, bg=Theme.CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL,
                                  command=self._canvas.yview)
        self._list_frame = tk.Frame(self._canvas, bg=Theme.CARD_BG)
        self._list_frame.bind("<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.create_window((0, 0), window=self._list_frame,
                                    anchor="nw", tags="list")
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_canvas_resize(event):
            self._canvas.itemconfig("list", width=event.width)
        self._canvas.bind("<Configure>", _on_canvas_resize)

        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind("<Enter>",
            lambda e: self._canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self._canvas.bind("<Leave>",
            lambda e: self._canvas.unbind_all("<MouseWheel>"))

        # Add button
        add_btn = tk.Label(self, text="+ 添加 Provider", bg=Theme.ACCENT,
                          fg="#ffffff", font=("Microsoft YaHei", 10, "bold"),
                          padx=12, pady=6, cursor="hand2")
        add_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        add_btn.bind("<Button-1>", lambda e: self.event_generate("<<AddProvider>>"))

    def set_providers(self, providers: list[dict]):
        self._providers = providers
        for f in self._item_frames:
            f.destroy()
        self._item_frames.clear()
        for i, p in enumerate(providers):
            self._add_item(i, p)

    def _add_item(self, index: int, provider: dict):
        bg = Theme.CARD_BG
        item = tk.Frame(self._list_frame, bg=bg,
                       highlightbackground=Theme.CARD_BORDER,
                       highlightthickness=1, padx=8, pady=6)
        item.pack(fill=tk.X, padx=6, pady=2)
        self._item_frames.append(item)

        enabled = provider.get("enabled", True)
        status_color = Theme.GREEN if enabled else Theme.TEXT_SEC
        status_text = "●" if enabled else "○"
        tk.Label(item, text=status_text, bg=bg, fg=status_color,
                font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0, 6))

        icon_key = provider.get("icon", "")
        icon_text = PROVIDER_ICONS.get(icon_key, "🔗")
        tk.Label(item, text=icon_text, bg=bg,
                font=("Segoe UI Emoji", 12)).pack(side=tk.LEFT, padx=(0, 4))

        label = provider.get("label", f"Provider {index+1}")
        tk.Label(item, text=label, bg=bg, fg=Theme.TEXT,
                font=("Microsoft YaHei", 10), anchor=tk.W).pack(
                side=tk.LEFT, fill=tk.X, expand=True)

        weight = provider.get("weight", 100)
        tk.Label(item, text=str(weight), bg=bg,
                fg=Theme.TEXT_SEC, font=("Consolas", 8)).pack(
                side=tk.RIGHT, padx=(4, 0))

        def on_click(e, idx=index):
            self.select(idx)

        for w in [item] + list(item.winfo_children()):
            w.bind("<Enter>", lambda e, f=item:
                f.configure(bg="#3c3c40") or [c.configure(bg="#3c3c40") for c in f.winfo_children()])
            w.bind("<Leave>", lambda e, f=item:
                f.configure(bg=Theme.CARD_BG) or [c.configure(bg=Theme.CARD_BG) for c in f.winfo_children()])
            w.bind("<Button-1>", on_click)

    def select(self, index: int):
        self._selected_index = index
        for i, f in enumerate(self._item_frames):
            bg = "#094771" if i == index else Theme.CARD_BG
            f.configure(bg=bg)
            for c in f.winfo_children():
                try: c.configure(bg=bg)
                except tk.TclError: pass
        self._on_select(index)

    @property
    def selected_index(self) -> int:
        return self._selected_index


class ModelFetchDialog:
    """Modal dialog for selecting fetched models."""

    def __init__(self, parent: tk.Toplevel, provider_name: str, models: list[str]):
        self.result: str | None = None
        self.top = tk.Toplevel(parent)
        self.top.title(f"可用模型 — {provider_name}")
        self.top.geometry("400x420")
        self.top.resizable(True, True)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.configure(bg=Theme.PAGE_BG)
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self._build(models)
        self.top.wait_window()

    def _build(self, models: list[str]):
        tk.Label(self.top, text="📥 选择模型", bg=Theme.PAGE_BG,
                fg=Theme.TEXT, font=("Microsoft YaHei", 12, "bold")).pack(
                fill=tk.X, padx=12, pady=(12, 8))

        list_frame = tk.Frame(self.top, bg=Theme.PAGE_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        scrollbar = ttk.Scrollbar(list_frame)
        self._listbox = tk.Listbox(list_frame, bg=Theme.INPUT_BG, fg=Theme.TEXT,
                                    selectbackground=Theme.ACCENT,
                                    selectforeground="#ffffff",
                                    font=("Consolas", 10),
                                    yscrollcommand=scrollbar.set,
                                    relief="flat", borderwidth=0,
                                    activestyle="none")
        for m in models:
            self._listbox.insert(tk.END, f"  {m}")

        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar.config(command=self._listbox.yview)

        self._listbox.bind("<Double-Button-1>", lambda e: self._on_confirm())
        self._listbox.bind("<Return>", lambda e: self._on_confirm())

        btn_frame = tk.Frame(self.top, bg=Theme.PAGE_BG)
        btn_frame.pack(fill=tk.X, padx=12, pady=(8, 12))

        cancel_btn = tk.Label(btn_frame, text="取消", bg=Theme.CARD_BG,
                             fg=Theme.TEXT, font=("Microsoft YaHei", 10),
                             padx=20, pady=4, cursor="hand2",
                             highlightbackground=Theme.CARD_BORDER,
                             highlightthickness=1)
        cancel_btn.pack(side=tk.RIGHT, padx=(8, 0))
        cancel_btn.bind("<Button-1>", lambda e: self._on_cancel())

        confirm_btn = tk.Label(btn_frame, text="确定", bg=Theme.ACCENT,
                              fg="#ffffff", font=("Microsoft YaHei", 10, "bold"),
                              padx=20, pady=4, cursor="hand2")
        confirm_btn.pack(side=tk.RIGHT)
        confirm_btn.bind("<Button-1>", lambda e: self._on_confirm())

    def _on_confirm(self):
        selection = self._listbox.curselection()
        if selection:
            self.result = self._listbox.get(selection[0]).strip()
        self.top.destroy()

    def _on_cancel(self):
        self.result = None
        self.top.destroy()


class SettingsWindow:
    """Main settings window with main-detail layout."""

    def __init__(self, parent: tk.Tk, cfg: AppConfig, overlay=None,
                 on_save_callback: Callable | None = None):
        self.cfg = cfg
        self.overlay = overlay
        self._on_save_callback = on_save_callback
        self.result: AppConfig | None = None

        self._providers: list[dict] = [
            dict(p) if isinstance(p, dict) else {
                "id": getattr(p, "id", ""),
                "label": getattr(p, "label", ""),
                "endpoint": getattr(p, "endpoint", ""),
                "api_key": getattr(p, "api_key", ""),
                "model": getattr(p, "model", ""),
                "enabled": getattr(p, "enabled", True),
                "preset_id": getattr(p, "preset_id", ""),
                "icon": getattr(p, "icon", ""),
                "api_format": getattr(p, "api_format", "openai"),
                "weight": getattr(p, "weight", 100),
                "extra_headers": getattr(p, "extra_headers", {}),
                "extra_body": getattr(p, "extra_body", {}),
                "timeout": getattr(p, "timeout", 8),
            }
            for p in cfg.llm_providers
        ]

        self.top = tk.Toplevel(parent)
        self.top.title("Settings / 设置")
        sw = getattr(cfg, "settings_win_w", 800) or 800
        sh = getattr(cfg, "settings_win_h", 600) or 600
        self.top.geometry(f"{sw}x{sh}")
        self.top.minsize(600, 400)
        self.top.resizable(True, True)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.configure(bg=Theme.PAGE_BG)
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.top.wait_window()

    def _build(self):
        self.top.columnconfigure(0, weight=0, minsize=200)
        self.top.columnconfigure(1, weight=3)
        self.top.rowconfigure(0, weight=1)

        self._list_panel = ProviderListPanel(
            self.top, on_select=self._on_provider_select)
        self._list_panel.grid(row=0, column=0, sticky="nsew")
        self._list_panel.bind("<<AddProvider>>", lambda e: self._on_add_provider())

        self._edit_panel = ProviderEditPanel(
            self.top,
            on_save=self._on_save_provider,
            on_delete=self._on_delete_provider,
            on_test=self._on_test_provider,
            on_fetch_models=self._on_fetch_models,
        )
        self._edit_panel.grid(row=0, column=1, sticky="nsew")

        self._list_panel.set_providers(self._providers)
        if self._providers:
            self._list_panel.select(0)

    def _on_provider_select(self, index: int):
        if 0 <= index < len(self._providers):
            self._edit_panel.load_provider(index, self._providers[index])

    def _on_add_provider(self):
        dialog = PresetSelectorDialog(self.top)
        if dialog.result is not None:
            data = dialog.result.to_provider_dict()
            self._providers.append(data)
            self._list_panel.set_providers(self._providers)
            self._list_panel.select(len(self._providers) - 1)
        elif dialog._custom_selected:
            self._providers.append({
                "id": f"manual_{len(self._providers)}",
                "label": f"Provider {len(self._providers) + 1}",
                "endpoint": "", "api_key": "", "model": "",
                "enabled": True, "preset_id": "", "icon": "custom",
                "api_format": "openai", "weight": 100,
                "extra_headers": {}, "extra_body": {}, "timeout": 8,
            })
            self._list_panel.set_providers(self._providers)
            self._list_panel.select(len(self._providers) - 1)

    def _on_save_provider(self):
        idx = self._list_panel.selected_index
        if 0 <= idx < len(self._providers):
            self._providers[idx] = self._edit_panel.gather_provider(idx)
            self._list_panel.set_providers(self._providers)
            self._list_panel.select(idx)

    def _on_delete_provider(self, index: int):
        if 0 <= index < len(self._providers):
            self._providers.pop(index)
            self._list_panel.set_providers(self._providers)
            if self._providers:
                self._list_panel.select(min(index, len(self._providers) - 1))
            else:
                self._edit_panel.clear()

    def _on_test_provider(self, index: int):
        if index < 0 or index >= len(self._providers):
            return
        p = self._edit_panel.gather_provider(index)
        endpoint = p["endpoint"]
        api_key = p["api_key"]
        timeout = p.get("timeout", 8)
        self._edit_panel.set_test_status("⏳ 正在测试...", ok=None)

        def run_test():
            result = test_connectivity(endpoint, api_key, timeout)
            if result.success:
                models_info = f" ({len(result.models)} 个模型)" if result.models else ""
                self.top.after(0, lambda: self._edit_panel.set_test_status(
                    f"✓ 连通 {result.latency_ms:.0f}ms{models_info}", ok=True))
            else:
                self.top.after(0, lambda: self._edit_panel.set_test_status(
                    f"✗ {result.error}", ok=False))

        threading.Thread(target=run_test, daemon=True).start()

    def _on_fetch_models(self, index: int):
        if index < 0 or index >= len(self._providers):
            return
        p = self._edit_panel.gather_provider(index)
        endpoint = p["endpoint"]
        api_key = p["api_key"]
        provider_name = p["label"] or f"Provider {index+1}"
        self._edit_panel.set_test_status("📥 正在拉取模型列表...", ok=None)

        def run_fetch():
            result = fetch_models(endpoint, api_key)
            if result.success and result.models:
                def show_dialog():
                    dialog = ModelFetchDialog(self.top, provider_name, result.models)
                    if dialog.result:
                        self._edit_panel._model_entry.delete(0, tk.END)
                        self._edit_panel._model_entry.insert(0, dialog.result)
                    self._edit_panel.set_test_status(
                        f"✓ 获取到 {len(result.models)} 个模型", ok=True)
                self.top.after(0, show_dialog)
            elif result.success and not result.models:
                self.top.after(0, lambda: self._edit_panel.set_test_status(
                    "⚠ 服务器可达但无模型列表", ok=None))
            else:
                self.top.after(0, lambda: self._edit_panel.set_test_status(
                    f"✗ {result.error}", ok=False))

        threading.Thread(target=run_fetch, daemon=True).start()

    def _on_close(self):
        import copy
        result_cfg = copy.deepcopy(self.cfg)
        result_cfg.llm_providers = list(self._providers)
        try:
            g = self.top.geometry()
            w_str, rest = g.split("x", 1)
            h_str = rest.split("+")[0].split("-")[0]
            result_cfg.settings_win_w = int(w_str)
            result_cfg.settings_win_h = int(h_str)
        except (ValueError, IndexError):
            pass

        self.result = result_cfg
        save_config(result_cfg)
        if self._on_save_callback:
            self._on_save_callback(result_cfg)
        self.top.destroy()
