"""
Hotkey manager — global hotkey polling, manual send hotkey detection.
Extracted from overlay.py for modularity.
"""
from __future__ import annotations

import ctypes
import threading
import tkinter as tk

from win32_constants import (
    MOD_SHIFT, MOD_CONTROL, MOD_ALT,
    VK_SHIFT, VK_CONTROL, VK_ALT,
    SPECIAL_VK,
)


class HotkeyManager:
    """Manages global hotkey polling for summoning the translator and detecting manual send keys."""

    def __init__(self, root: tk.Tk, cfg, focus_callback: callable):
        self.root = root
        self.cfg = cfg
        self._focus_callback = focus_callback
        self._hotkey_active = False
        self._manual_poller_active = False
        self.send_hint: tk.Label | None = None
        self._pending_english = ""
        self._pending_chinese = ""

    # ── Hotkey display helpers ──

    @staticmethod
    def format_hotkey(raw: str) -> str:
        parts = [p.strip().title() for p in raw.strip().split("+")]
        return "+".join(parts)

    def update_hint_text(self, text: str, fg: str = "#888888") -> None:
        if self.send_hint:
            self.send_hint.config(text=text, fg=fg)

    def reset_hint(self) -> None:
        if self.send_hint:
            self.send_hint.config(
                text=f" {self.format_hotkey(self.cfg.send_hotkey)} ...",
                fg="#888888",
            )

    # ── Hotkey parsing ──

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

    def _parse_hotkey_vk(self, hotkey_str: str) -> tuple[int, int]:
        """Parse hotkey string into (mods_mask, vk_code). Supports special keys."""
        parts = hotkey_str.lower().strip().split("+")
        mods = 0
        for p in parts[:-1]:
            p = p.strip()
            if p in ("shift", "shft"): mods |= MOD_SHIFT
            elif p in ("ctrl", "control"): mods |= MOD_CONTROL
            elif p in ("alt"): mods |= MOD_ALT
        key = parts[-1].strip()
        if key in SPECIAL_VK:
            vk = SPECIAL_VK[key]
        elif len(key) == 1:
            vk = ord(key.upper())
        else:
            vk = 0
        return mods, vk

    @staticmethod
    def _mod_vks(mods: int) -> list[int]:
        """Convert MOD_* flags to VK codes for GetAsyncKeyState."""
        vks: list[int] = []
        if mods & MOD_SHIFT: vks.append(VK_SHIFT)
        if mods & MOD_CONTROL: vks.append(VK_CONTROL)
        if mods & MOD_ALT: vks.append(VK_ALT)
        return vks

    # ── Global hotkey poller (summon input) ──

    def start(self) -> None:
        """Start background thread polling for the send hotkey."""
        mods, vk = self._parse_hotkey(self.cfg.send_hotkey)
        if vk == 0:
            return

        self._hotkey_active = True

        def poller():
            mod_vks = self._mod_vks(mods)

            def held(vk_code):
                return ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000

            was_down = all(held(mv) for mv in mod_vks) and held(vk)
            while self._hotkey_active:
                mods_ok = all(held(mv) for mv in mod_vks) if mod_vks else True
                key_down = held(vk)
                combo = mods_ok and key_down

                if combo and not was_down:
                    self.root.after(0, self._focus_callback)
                was_down = combo
                threading.Event().wait(0.05)

        t = threading.Thread(target=poller, daemon=True)
        t.start()

    def stop(self) -> None:
        """Stop the global hotkey poller."""
        self._hotkey_active = False

    def update_send_hotkey(self, new_hotkey: str) -> None:
        """Called when user changes the hotkey in settings."""
        self._hotkey_active = False  # stop current poller
        self.cfg.send_hotkey = new_hotkey
        self.reset_hint()
        self.start()

    # ── Manual send hotkey poller ──

    def start_manual_send(self, pending_chinese: str, pending_english: str) -> None:
        """Start background thread polling copy/enter hotkeys."""
        if self._manual_poller_active:
            return
        self._manual_poller_active = True
        self._pending_chinese = pending_chinese
        self._pending_english = pending_english

        copy_mods, copy_vk = self._parse_hotkey_vk(self.cfg.copy_hotkey)
        enter_mods, enter_vk = self._parse_hotkey_vk(self.cfg.enter_hotkey)

        def held(vk_code):
            return ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000

        def check(mods, vk):
            if vk == 0:
                return False
            mv = self._mod_vks(mods)
            return all(held(mv) for mv in mv) and held(vk)

        was_copy = check(copy_mods, copy_vk)
        was_enter = check(enter_mods, enter_vk)

        def poller():
            nonlocal was_copy, was_enter
            while self._manual_poller_active:
                cd = check(copy_mods, copy_vk)
                ed = check(enter_mods, enter_vk)

                if cd and not was_copy:
                    self.root.after(0, self._on_copy)
                if ed and not was_enter:
                    self.root.after(0, self._on_enter)

                was_copy, was_enter = cd, ed
                threading.Event().wait(0.05)

        t = threading.Thread(target=poller, daemon=True)
        t.start()

    def stop_manual_send(self) -> None:
        self._manual_poller_active = False

    # Callback stubs — set these after construction
    on_copy: callable = lambda self: None
    on_enter: callable = lambda self: None

    def _on_copy(self) -> None:
        self.on_copy()

    def _on_enter(self) -> None:
        self.on_enter()
