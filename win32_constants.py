"""
Shared Win32 API constants, structs, and helper types.
Used by tray_icon.py, overlay.py, input_sender.py to avoid duplication.
"""
import ctypes
from ctypes import wintypes

# ── Window styles ──
GWL_EXSTYLE = -20
GWLP_WNDPROC = -4
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_OVERLAPPED = 0x00000000
CW_USEDEFAULT = 0x80000000
COLOR_WINDOW = 5

# ── Window messages ──
WM_USER = 0x0400
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_HOTKEY = 0x0312
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202

# ── System tray (Shell_NotifyIcon) ──
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_STATE = 0x00000008
NIS_HIDDEN = 0x00000001

# ── Icon / image ──
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
IDI_APPLICATION = 32512

# ── Menu ──
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008
MF_UNCHECKED = 0x00000000
MF_DEFAULT = 0x00001000
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

# ── GDI ──
BS_PATTERN = 3
HS_VERTICAL = 1

# ── Keyboard input (SendInput) ──
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# ── Virtual key codes ──
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_V = 0x56
VK_ESCAPE = 0x1B
VK_SHIFT = 0x10
VK_ALT = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_TAB = 0x09
VK_SPACE = 0x20
VK_BACKSPACE = 0x08
VK_DELETE = 0x2E
VK_HOME = 0x24
VK_END = 0x23
VK_PGUP = 0x21
VK_PGDN = 0x22
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_UP = 0x26
VK_DOWN = 0x28
VK_INSERT = 0x2D

# ── Modifier flags ──
MOD_SHIFT = 0x0004
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001

# ── Hotkey IDs ──
HOTKEY_SEND_ID = 1

# ── Key name → VK mapping ──
KEY_NAME_MAP: dict[str, int] = {
    "enter": VK_RETURN, "return": VK_RETURN,
    "esc": VK_ESCAPE, "escape": VK_ESCAPE,
    "ctrl": VK_CONTROL, "control": VK_CONTROL,
    "tab": VK_TAB, "space": VK_SPACE,
    "backspace": VK_BACKSPACE, "bs": VK_BACKSPACE,
    "delete": VK_DELETE, "del": VK_DELETE,
    "home": VK_HOME, "end": VK_END,
    "pgup": VK_PGUP, "pgdn": VK_PGDN,
    "left": VK_LEFT, "right": VK_RIGHT,
    "up": VK_UP, "down": VK_DOWN,
    "insert": VK_INSERT, "ins": VK_INSERT,
}

_MOD_VK_MAP: dict[str, int] = {
    "shift": VK_SHIFT, "shft": VK_SHIFT,
    "ctrl": VK_CONTROL, "control": VK_CONTROL,
    "alt": VK_ALT,
    "win": VK_LWIN, "windows": VK_LWIN,
}

SPECIAL_VK: dict[str, int] = {
    **KEY_NAME_MAP,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}

# ── Win32 structs ──


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", wintypes.BYTE * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


# ── Helper functions ──


def vk_code(key: str) -> int:
    """Convert a key string to virtual key code."""
    key_lower = key.lower().strip()
    if key_lower in KEY_NAME_MAP:
        return KEY_NAME_MAP[key_lower]
    if key_lower in SPECIAL_VK:
        return SPECIAL_VK[key_lower]
    if len(key_lower) == 1:
        return ord(key_lower.upper())
    return 0


def mod_vk(mods: int) -> list[int]:
    """Convert MOD_* flags to VK codes for GetAsyncKeyState."""
    vks: list[int] = []
    if mods & MOD_SHIFT:
        vks.append(VK_SHIFT)
    if mods & MOD_CONTROL:
        vks.append(VK_CONTROL)
    if mods & MOD_ALT:
        vks.append(VK_ALT)
    return vks
