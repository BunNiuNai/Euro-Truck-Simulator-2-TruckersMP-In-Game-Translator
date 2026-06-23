"""
Hotkey manager — system-level RegisterHotKey via Win32 message window
for the summon hotkey. Manual send (copy/enter) hotkeys still use polling.
"""
from __future__ import annotations

import ctypes
import threading
import tkinter as tk
from ctypes import wintypes

from win32_constants import (
    MOD_SHIFT, MOD_CONTROL, MOD_ALT,
    VK_SHIFT, VK_CONTROL, VK_ALT,
    SPECIAL_VK,
)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_HOTKEY = 0x0312
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010

MOD_VK_MAP = {MOD_SHIFT: VK_SHIFT, MOD_CONTROL: VK_CONTROL, MOD_ALT: VK_ALT}


class HotkeyManager:
    """Manages system-level hotkey via RegisterHotKey and a hidden message window."""

    def __init__(self, root: tk.Tk, cfg, focus_callback: callable):
        self.root = root
        self.cfg = cfg
        self._focus_callback = focus_callback
        self._hwnd: int | None = None
        self._hotkey_id = 1
        self._thread: threading.Thread | None = None
        self._running = False
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

    # ── System-level hotkey via RegisterHotKey ──

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_HOTKEY:
            self.root.after(0, self._focus_callback)
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self) -> None:
        """Thread entry: create hidden window, register hotkey, run message loop."""
        hinst = kernel32.GetModuleHandleW(None)
        class_name = "ETS2HotkeyWindow"

        wnd_proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )
        self._wnd_proc_ref = wnd_proc_type(self._wnd_proc)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("style", wintypes.UINT),
                ("lpfnWndProc", wintypes.LPVOID),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HCURSOR),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON),
            ]

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._wnd_proc_ref, wintypes.LPVOID)
        wc.hInstance = hinst
        wc.lpszClassName = class_name

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            return

        self._hwnd = user32.CreateWindowExW(
            0, class_name, "ETS2Hotkey",
            0, 0, 0, 0, 0,
            wintypes.HWND(-3), 0, hinst, 0,
        )
        if not self._hwnd:
            return

        mods, vk = self._parse_hotkey(self.cfg.send_hotkey)
        if vk != 0:
            ok = user32.RegisterHotKey(self._hwnd, self._hotkey_id, mods, vk)
            if not ok:
                # Some combos reserved by OS — fall back to alt+key
                if mods & MOD_SHIFT:
                    mods = (mods & ~MOD_SHIFT) | MOD_ALT
                    ok = user32.RegisterHotKey(self._hwnd, self._hotkey_id, mods, vk)
                if not ok:
                    user32.DestroyWindow(self._hwnd)
                    self._hwnd = None
                    return

        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hwnd:
            user32.UnregisterHotKey(self._hwnd, self._hotkey_id)
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def update_send_hotkey(self, new_hotkey: str) -> None:
        """Re-register hotkey after user changes the combo."""
        self.stop()
        self.cfg.send_hotkey = new_hotkey
        self.reset_hint()
        self.start()
