"""
Acrylic / Mica frosted-glass helper for Tkinter borderless windows.
Applies the best available effect based on Windows version:
  - Win11 22621+: DWM system backdrop (Mica / Acrylic via DwmSetWindowAttribute)
  - Win10 1803+: Acrylic blur via SetWindowCompositionAttribute
  - Older:     semi-transparent solid background fallback

Usage:
    from acrylic_helper import apply_acrylic

    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg="#1a1a2e")
    root.after(50, lambda: apply_acrylic(root))
"""
from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes

# ── OS version detection via RtlGetVersion (unaffected by app manifest) ──

class _OSVERSIONINFOEXW(ctypes.Structure):
    _fields_ = [
        ("dwOSVersionInfoSize", ctypes.c_ulong),
        ("dwMajorVersion",      ctypes.c_ulong),
        ("dwMinorVersion",      ctypes.c_ulong),
        ("dwBuildNumber",       ctypes.c_ulong),
        ("dwPlatformId",        ctypes.c_ulong),
        ("szCSDVersion",        ctypes.c_wchar * 128),
        ("wServicePackMajor",   ctypes.c_ushort),
        ("wServicePackMinor",   ctypes.c_ushort),
        ("wSuiteMask",          ctypes.c_ushort),
        ("wProductType",        ctypes.c_byte),
        ("wReserved",           ctypes.c_byte),
    ]


def _get_build() -> int:
    """Return the real Windows build number."""
    info = _OSVERSIONINFOEXW()
    info.dwOSVersionInfoSize = ctypes.sizeof(info)
    ret = ctypes.windll.ntdll.RtlGetVersion(ctypes.byref(info))
    if ret != 0:
        return 0
    return info.dwBuildNumber


_WIN11_22621 = 22621   # build where DWMWA_SYSTEMBACKDROP_TYPE became available
_WIN10_1803  = 17134   # build where ACCENT_ENABLE_ACRYLICBLURBEHIND was added


# ── Path A: SetWindowCompositionAttribute (Win10 Acrylic) ──

ACCENT_DISABLED                   = 0
ACCENT_ENABLE_GRADIENT            = 1
ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
ACCENT_ENABLE_BLURBEHIND          = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND   = 4
ACCENT_ENABLE_HOSTBACKDROP        = 5
WCA_ACCENT_POLICY                 = 19


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState",   wintypes.DWORD),
        ("AccentFlags",   wintypes.DWORD),
        ("GradientColor", wintypes.DWORD),  # 0xAABBGGRR
        ("AnimationId",   wintypes.DWORD),
    ]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute",  ctypes.c_int),
        ("Data",       ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _apply_accent_acrylic(hwnd: int, gradient_color: int = 0x701A1A2E) -> bool:
    """Apply Win10 acrylic blur via SetWindowCompositionAttribute.

    Args:
        hwnd: Window handle.
        gradient_color: 0xAABBGGRR tint. Default = 70% dark blue-gray (#1a1a2e).
    """
    user32 = ctypes.windll.user32
    SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
    SetWindowCompositionAttribute.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(_WINDOWCOMPOSITIONATTRIBDATA),
    ]
    SetWindowCompositionAttribute.restype = wintypes.BOOL

    policy = _ACCENT_POLICY()
    policy.AccentState   = ACCENT_ENABLE_ACRYLICBLURBEHIND
    policy.AccentFlags   = 2  # draw all borders
    policy.GradientColor = gradient_color
    policy.AnimationId   = 0

    data = _WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute  = WCA_ACCENT_POLICY
    data.SizeOfData = ctypes.sizeof(policy)
    data.Data       = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)

    return bool(SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.byref(data)))


def _apply_accent_disabled(hwnd: int) -> bool:
    """Remove acrylic/blur (restore normal window rendering)."""
    user32 = ctypes.windll.user32
    SetWindowCompositionAttribute = user32.SetWindowCompositionAttribute
    SetWindowCompositionAttribute.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(_WINDOWCOMPOSITIONATTRIBDATA),
    ]
    SetWindowCompositionAttribute.restype = wintypes.BOOL

    policy = _ACCENT_POLICY()
    policy.AccentState = ACCENT_DISABLED
    data = _WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute  = WCA_ACCENT_POLICY
    data.SizeOfData = ctypes.sizeof(policy)
    data.Data       = ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p)

    return bool(SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.byref(data)))


# ── Path B: DwmSetWindowAttribute (Win11 Mica / Acrylic) ──

DWMWA_SYSTEMBACKDROP_TYPE = 38    # Win11 22621+
DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Win10 1809+

DWMSBT_AUTO            = 0
DWMSBT_NONE            = 1
DWMSBT_MAINWINDOW      = 2   # Mica
DWMSBT_TRANSIENTWINDOW = 3   # Acrylic
DWMSBT_TABBEDWINDOW    = 4   # Mica Alt


class _MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth",   ctypes.c_int),
        ("cxRightWidth",  ctypes.c_int),
        ("cyTopHeight",   ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


def _apply_dwm_backdrop(hwnd: int, backdrop_type: int = DWMSBT_MAINWINDOW) -> bool:
    """Apply Win11 Mica/Acrylic via DwmSetWindowAttribute.

    Also extends the DWM frame into the entire client area so the backdrop
    covers the whole borderless window.
    """
    dwmapi = ctypes.windll.dwmapi

    # 1. Set the system backdrop type
    dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd),
        wintypes.DWORD(DWMWA_SYSTEMBACKDROP_TYPE),
        ctypes.byref(ctypes.c_int(backdrop_type)),
        ctypes.sizeof(ctypes.c_int()),
    )

    # 2. Extend frame into the entire client area (-1 margins = full coverage)
    margins = _MARGINS(-1, -1, -1, -1)
    dwmapi.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins))

    # 3. Enable dark mode (best-effort, attribute 20 only available on Win10 1809+)
    try:
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(ctypes.c_int(1)),
            ctypes.sizeof(ctypes.c_int()),
        )
    except Exception:
        pass

    return True


# ── HWND acquisition ──

def _get_real_hwnd(root: tk.Tk) -> int:
    """Get the real top-level HWND from a Tkinter Tk window.

    root.winfo_id() returns Tk's internal child; GetParent gives the
    true top-level window handle required by DWM/SetWindowComposition.
    """
    root.update_idletasks()
    return ctypes.windll.user32.GetParent(root.winfo_id())


# ── Public API ──

def apply_acrylic(
    root: tk.Tk,
    effect: str = "auto",
    gradient_color: int = 0x701A1A2E,
) -> bool:
    """Apply the best available frosted-glass effect to a Tkinter window.

    Call this AFTER the window is mapped (e.g. via root.after(50, ...)).

    Args:
        root: A Tkinter Tk instance (should already be visible).
        effect: "mica", "acrylic", or "auto" (best available, default).
        gradient_color: 0xAABBGGRR tint for the Win10 acrylic fallback.
                        Default is 70% opacity dark blue-gray (#1a1a2e).

    Returns:
        True if an effect was applied, False if all paths failed (rare).
    """
    hwnd = _get_real_hwnd(root)
    if not hwnd:
        return False

    build = _get_build()

    # Path 1: Win11 22621+ — modern DWM backdrop
    if build >= _WIN11_22621:
        if effect == "acrylic":
            bt = DWMSBT_TRANSIENTWINDOW
        elif effect == "mica":
            bt = DWMSBT_MAINWINDOW
        else:  # auto
            bt = DWMSBT_MAINWINDOW  # Mica is the best default on Win11
        try:
            return _apply_dwm_backdrop(hwnd, bt)
        except Exception:
            pass  # fall through to Win10 path

    # Path 2: Win10 1803+ — undocumented acrylic blur
    if build >= _WIN10_1803:
        try:
            return _apply_accent_acrylic(hwnd, gradient_color)
        except Exception:
            pass

    # Path 3: Nothing available — caller should fall back to semi-transparent alpha
    return False


def remove_acrylic(root: tk.Tk) -> None:
    """Remove any applied frosted-glass effect, restoring normal rendering."""
    hwnd = _get_real_hwnd(root)
    if not hwnd:
        return
    build = _get_build()

    try:
        if build >= _WIN11_22621:
            _apply_dwm_backdrop(hwnd, DWMSBT_NONE)
        else:
            _apply_accent_disabled(hwnd)
    except Exception:
        pass
