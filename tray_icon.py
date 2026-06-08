"""
Minimal system tray icon using pure ctypes + Win32 API.
Avoids pystray which is incompatible with Python 3.14 free-threading.
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from win32_constants import (
    WM_USER, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_LBUTTONUP,
    WM_COMMAND, WM_DESTROY, WM_CLOSE,
    NIM_ADD, NIM_MODIFY, NIM_DELETE,
    NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_STATE, NIS_HIDDEN,
    IMAGE_ICON, LR_LOADFROMFILE, IDI_APPLICATION,
    MF_STRING, MF_SEPARATOR, MF_CHECKED, MF_UNCHECKED, MF_DEFAULT,
    TPM_RIGHTBUTTON, TPM_RETURNCMD,
    CW_USEDEFAULT, WS_OVERLAPPED, COLOR_WINDOW,
    NOTIFYICONDATAW, ICONINFO, RECT,
)

# Project-specific constant
WM_TRAYICON = WM_USER + 1

# Win32 API bindings
user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Set argtypes/restype for critical functions to avoid ctypes conversion errors on 64-bit
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_longlong
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL


def _create_icon_simple() -> int:
    """Create a simple 32x32 icon with GDI - returns HICON."""
    hdc = user32.GetDC(0)
    mem_dc = gdi32.CreateCompatibleDC(hdc)

    # Create color bitmap (32x32, 32-bit)
    bm = gdi32.CreateCompatibleBitmap(hdc, 32, 32)
    old_bm = gdi32.SelectObject(mem_dc, bm)

    # Fill background
    bg = gdi32.CreateSolidBrush(0x1e1e1e)  # dark bg
    r = RECT(0, 0, 32, 32)
    user32.FillRect(mem_dc, ctypes.byref(r), bg)
    gdi32.DeleteObject(bg)

    # Colored square
    inner = gdi32.CreateSolidBrush(0xd69c56)  # BGR #569cd6
    r2 = RECT(4, 4, 28, 28)
    user32.FillRect(mem_dc, ctypes.byref(r2), inner)
    gdi32.DeleteObject(inner)

    # Text
    gdi32.SetBkMode(mem_dc, 1)
    gdi32.SetTextColor(mem_dc, 0xFFFFFF)
    font = gdi32.CreateFontW(18, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 0, 0, "Microsoft YaHei")
    old_font = gdi32.SelectObject(mem_dc, font)
    tr = RECT(0, 4, 32, 32)
    user32.DrawTextW(mem_dc, "T", 1, ctypes.byref(tr), 0x0001 | 0x0100)
    gdi32.SelectObject(mem_dc, old_font)
    gdi32.DeleteObject(font)

    # Get bitmap bits
    bmp_bits = (wintypes.BYTE * (32 * 32 * 4))()
    gdi32.GetBitmapBits(bm, ctypes.sizeof(bmp_bits), bmp_bits)

    # Create mask bitmap (1bpp, all white = all pixels visible)
    mask_dc = gdi32.CreateCompatibleDC(hdc)
    mask_bm = gdi32.CreateBitmap(32, 32, 1, 1, None)
    old_mask_bm = gdi32.SelectObject(mask_dc, mask_bm)
    # Fill with white (all bits = 1)
    white_brush = gdi32.CreateSolidBrush(0xFFFFFF)
    mask_r = RECT(0, 0, 32, 32)
    user32.FillRect(mask_dc, ctypes.byref(mask_r), white_brush)
    gdi32.DeleteObject(white_brush)

    mask_bits = (wintypes.BYTE * (32 * 4))()
    gdi32.GetBitmapBits(mask_bm, ctypes.sizeof(mask_bits), mask_bits)

    ii = ICONINFO()
    ii.fIcon = True
    ii.xHotspot = 0
    ii.yHotspot = 0
    ii.hbmColor = bm
    ii.hbmMask = mask_bm

    hicon = user32.CreateIconIndirect(ctypes.byref(ii))

    # Cleanup
    gdi32.SelectObject(mask_dc, old_mask_bm)
    gdi32.DeleteObject(mask_bm)
    gdi32.DeleteDC(mask_dc)
    gdi32.SelectObject(mem_dc, old_bm)
    gdi32.DeleteObject(bm)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(0, hdc)

    return hicon


class TrayIcon:
    """Minimal system tray icon using Win32 API directly."""

    def __init__(self, title: str = "ETS2 聊天翻译器") -> None:
        self._title = title
        self._hwnd: int | None = None
        self._hicon: int | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._menu_items: list[dict] = []
        self._next_menu_id = 1000
        self._default_cb: callable | None = None

    def set_menu(self, items: list[dict], default_cb: callable | None = None) -> None:
        """Set the right-click menu.

        items: list of dicts:
            {"label": str, "callback": callable, "checked": callable|None}
            or ("---",) for separator
        default_cb: called on double-click or single left-click
        """
        self._menu_items = []
        self._next_menu_id = 1000
        for item in items:
            if isinstance(item, dict):
                mid = self._next_menu_id
                self._next_menu_id += 1
                self._menu_items.append({
                    "id": mid,
                    "label": item["label"],
                    "callback": item.get("callback"),
                    "checked_fn": item.get("checked"),
                    "default": item.get("default", False),
                })
            else:
                self._menu_items.append({"id": 0, "label": "---", "separator": True})
        self._default_cb = default_cb

    def start(self) -> None:
        """Create tray icon and start message pump in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Remove tray icon and stop message pump."""
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        if msg == WM_TRAYICON:
            if lparam == WM_RBUTTONUP:
                self._show_menu()
            elif lparam == WM_LBUTTONDBLCLK or lparam == WM_LBUTTONUP:
                if self._default_cb:
                    self._default_cb()
            return 0
        elif msg == WM_COMMAND:
            mid = wparam & 0xFFFF
            for item in self._menu_items:
                if item.get("id") == mid and item.get("callback"):
                    item["callback"]()
                    break
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self) -> None:
        # Register window class
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

        hinst = kernel32.GetModuleHandleW(None)
        class_name = "ETS2TrayIconClass"

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._wnd_proc_ref, wintypes.LPVOID)
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        wc.hbrBackground = wintypes.HBRUSH(COLOR_WINDOW + 1)

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            return

        # Create hidden message-only window
        self._hwnd = user32.CreateWindowExW(
            0, class_name, "ETS2Tray",
            WS_OVERLAPPED,
            0, 0, 0, 0,
            0, 0, hinst, 0
        )

        if not self._hwnd:
            return

        # Create icon
        self._hicon = _create_icon_simple()

        # Add tray icon
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon or user32.LoadIconW(0, IDI_APPLICATION)
        nid.szTip = self._title

        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

        # Message loop
        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Remove tray icon
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

        # Destroy icon
        if self._hicon:
            user32.DestroyIcon(self._hicon)
            self._hicon = None

        # Destroy window
        if self._hwnd:
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def _show_menu(self) -> None:
        if not self._menu_items:
            return

        # Create popup menu
        menu = user32.CreatePopupMenu()

        for item in self._menu_items:
            if item.get("separator"):
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, 0)
            else:
                flags = MF_STRING
                if item.get("default"):
                    flags |= MF_DEFAULT

                # Check if item should be checked
                if item.get("checked_fn"):
                    try:
                        is_checked = item["checked_fn"]()
                    except Exception:
                        is_checked = False
                    if is_checked:
                        flags |= MF_CHECKED

                user32.AppendMenuW(menu, flags, item["id"], item["label"])

        # Get cursor position
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))

        # Required: give the popup menu focus so it receives clicks
        user32.SetForegroundWindow(self._hwnd)

        # Track menu
        cmd = user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
            pt.x, pt.y, 0, self._hwnd, 0
        )

        # Execute command
        if cmd:
            user32.PostMessageW(self._hwnd, WM_COMMAND, cmd, 0)

        user32.DestroyMenu(menu)

    def modify_tip(self, tip: str) -> None:
        """Update the tooltip text."""
        if not self._hwnd:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_TIP
        nid.szTip = tip
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
