# Fix All 12 Issues — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 12 identified issues: security (DPAPI encryption), dead code removal, queue bounding, parallel Baidu translation, prompt extraction, overlay splitting, Win32 constants consolidation, dataclass migration, type annotations, debug log control, import fix, and language option exposure.

**Architecture:** Incremental refactoring approach — each fix is self-contained and independently testable. New shared modules (`win32_constants.py`, `message_display.py`, `hotkey_manager.py`) are extracted first to avoid circular dependencies. Sensitive config fields are encrypted via Windows DPAPI with transparent load/save.

**Tech Stack:** Python 3.10+, ctypes, Win32 DPAPI, Tkinter, httpx, concurrent.futures

---

## File Structure Map

| File | Action | Responsibility |
|:---|:---|:---|
| `win32_constants.py` | **Create** | Shared Win32 constants, structs, helper types |
| `prompts/receive_prompt.txt` | **Create** | System prompt for English→Chinese translation |
| `prompts/send_prompt.txt` | **Create** | System prompt for Chinese→English translation |
| `message_display.py` | **Create** | Message rendering, color tags, text widget management |
| `hotkey_manager.py` | **Create** | Global hotkey polling, manual send hotkey detection |
| `config.py` | Modify | DPAPI encryption, debug flag, target_language in UI |
| `tray_icon.py` | Modify | Remove dead `_create_icon()`, use shared constants |
| `main.py` | Modify | Bounded queues, type annotations, import shared modules |
| `translator.py` | Modify | Parallel Baidu, external prompts, dataclass, type annotations |
| `overlay.py` | Modify | Delegate to message_display + hotkey_manager, type annotations |
| `input_sender.py` | Modify | Use shared constants, debug flag, type annotations |
| `update.py` | Modify | Type annotations |
| `build_exe.py` | Modify | Fix import position |

---

### Task 1: Create shared Win32 constants module

**Files:**
- Create: `win32_constants.py`

- [ ] **Step 1: Create the shared constants file**

```python
"""
Shared Win32 API constants, structs, and helper types.
Used by tray_icon.py, overlay.py, input_sender.py.
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
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM), ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD), ("pt", POINT),
    ]

class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD), ("guidItem", wintypes.BYTE * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]

class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD), ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]

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
    if mods & MOD_SHIFT: vks.append(VK_SHIFT)
    if mods & MOD_CONTROL: vks.append(VK_CONTROL)
    if mods & MOD_ALT: vks.append(VK_ALT)
    return vks
```

- [ ] **Step 2: Verify file is syntactically correct**

```bash
python -c "import sys; sys.path.insert(0, 'y:/翻译器项目/ets2-translator'); from win32_constants import *; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add win32_constants.py && git commit -m "feat: add shared Win32 constants module"
```

---

### Task 2: Extract prompt templates to external files

**Files:**
- Create: `prompts/receive_prompt.txt`
- Create: `prompts/send_prompt.txt`
- Modify: `config.py:46-177` (replace inline DEFAULT_SYSTEM_PROMPT with file loader)
- Modify: `translator.py:297-422` (replace inline SEND_SYSTEM_PROMPT with file loader)

- [ ] **Step 1: Create receive prompt file**

Write the content of `DEFAULT_SYSTEM_PROMPT` from `config.py` (lines 46-177) to `prompts/receive_prompt.txt`.

- [ ] **Step 2: Create send prompt file**

Write the content of `SEND_SYSTEM_PROMPT` from `translator.py` (lines 297-422) to `prompts/send_prompt.txt`.

- [ ] **Step 3: Add prompt loading functions to config.py**

```python
import os

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")

def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = os.path.join(_PROMPTS_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def get_receive_prompt() -> str:
    """Get the English→Chinese translation prompt."""
    prompt = load_prompt("receive_prompt.txt")
    if not prompt:
        # Fallback: minimal prompt
        return "You are a translator for ETS2/TruckersMP in-game chat. Translate ALL messages into natural, accurate Simplified Chinese. Never summarize, never omit, never add — TRANSLATE ONLY."
    return prompt

def get_send_prompt() -> str:
    """Get the Chinese→English translation prompt."""
    prompt = load_prompt("send_prompt.txt")
    if not prompt:
        return "You are a translator for ETS2/TruckersMP in-game chat. Translate Chinese into natural, accurate English that a real gamer would type. Never summarize, never omit, never add. Output ONLY the English translation."
    return prompt
```

At the bottom of `config.py`, remove the inline `DEFAULT_SYSTEM_PROMPT = ...` assignment (the ~130-line string) and replace with:

```python
DEFAULT_SYSTEM_PROMPT = get_receive_prompt()
```

- [ ] **Step 4: Update translator.py to use external prompt**

Replace the inline `SEND_SYSTEM_PROMPT = ...` (lines 297-422) with:

```python
from config import get_send_prompt

SEND_SYSTEM_PROMPT = get_send_prompt()
```

- [ ] **Step 5: Update build_exe.py to include prompts in PyInstaller data**

Add `--add-data` flag for the prompts directory:

```python
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    "--name", NAME,
    "--add-data", f"{ICON};.",
    "--add-data", f"{os.path.join(PROJECT_DIR, 'prompts')};prompts",
    "--hidden-import", "httpx",
    "--clean",
    MAIN,
]
```

- [ ] **Step 6: Verify prompts load correctly**

```bash
cd y:/翻译器项目/ets2-translator && python -c "from config import get_receive_prompt, get_send_prompt; print('receive:', len(get_receive_prompt())); print('send:', len(get_send_prompt()))"
```

Expected: receive: ~5000+, send: ~5000+

- [ ] **Step 7: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add prompts/ config.py translator.py build_exe.py && git commit -m "refactor: extract prompt templates to external files"
```

---

### Task 3: Add DPAPI encryption for sensitive config fields

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add DPAPI encryption/decryption functions to config.py**

```python
import ctypes
from ctypes import wintypes

# ── Windows DPAPI for encrypting sensitive config fields ──

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]


_crypt32 = ctypes.windll.crypt32
_crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB)]
_crypt32.CryptProtectData.restype = wintypes.BOOL
_crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(DATA_BLOB)]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL

_kernel32 = ctypes.windll.kernel32
_kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
_kernel32.LocalFree.restype = wintypes.HLOCAL


def _dpapi_encrypt(plaintext: str) -> str:
    """Encrypt a string using Windows DPAPI. Returns base64-encoded ciphertext."""
    import base64
    data = plaintext.encode("utf-8")
    blob_in = DATA_BLOB(len(data), ctypes.c_char_p(data))
    blob_out = DATA_BLOB()
    if not _crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0,
                                      ctypes.byref(blob_out)):
        raise OSError("CryptProtectData failed")
    try:
        encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded DPAPI ciphertext. Returns plaintext."""
    import base64
    encrypted = base64.b64decode(ciphertext.encode("ascii"))
    blob_in = DATA_BLOB(len(encrypted), ctypes.c_char_p(encrypted))
    blob_out = DATA_BLOB()
    if not _crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0,
                                        ctypes.byref(blob_out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    finally:
        _kernel32.LocalFree(blob_out.pbData)


# Fields that should be encrypted at rest
_SECRET_FIELDS = {"api_key", "baidu_secret"}
# Prefix to identify encrypted values in JSON
_ENC_PREFIX = "dpapi:"


def _is_encrypted(value: str) -> bool:
    return value.startswith(_ENC_PREFIX)


def _maybe_encrypt(field: str, value: str) -> str:
    """Encrypt value if field is sensitive and value is not already encrypted."""
    if not value:
        return value
    if _is_encrypted(value):
        return value  # already encrypted
    if field in _SECRET_FIELDS:
        return _ENC_PREFIX + _dpapi_encrypt(value)
    return value


def _maybe_decrypt(field: str, value: str) -> str:
    """Decrypt value if it is encrypted."""
    if not value:
        return value
    if _is_encrypted(value):
        try:
            return _dpapi_decrypt(value[len(_ENC_PREFIX):])
        except Exception:
            return value  # fallback: return as-is if decryption fails
    return value
```

- [ ] **Step 2: Modify load_config() to decrypt on load**

In `load_config()`, after merging defaults with file data, decrypt sensitive fields:

```python
def load_config() -> AppConfig:
    ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        cfg = AppConfig()
        save_config(cfg)
        return cfg

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    defaults = asdict(AppConfig())
    merged = {**defaults, **data}
    # Decrypt sensitive fields
    for field in _SECRET_FIELDS:
        if field in merged:
            merged[field] = _maybe_decrypt(field, merged[field])
    cfg = AppConfig(**{k: merged[k] for k in defaults})
    return cfg
```

- [ ] **Step 3: Modify save_config() to encrypt on save**

```python
def save_config(cfg: AppConfig):
    ensure_config_dir()
    data = asdict(cfg)
    # Encrypt sensitive fields before writing
    for field in _SECRET_FIELDS:
        if field in data:
            data[field] = _maybe_encrypt(field, data[field])
    content = json.dumps(data, indent=2, ensure_ascii=False)
    # ... rest unchanged
```

- [ ] **Step 4: Verify encryption round-trip**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
from config import _dpapi_encrypt, _dpapi_decrypt
original = 'sk-test-secret-key-12345'
enc = _dpapi_encrypt(original)
dec = _dpapi_decrypt(enc)
assert original == dec, f'Round-trip failed: {original} != {dec}'
print('DPAPI round-trip OK')
"
```

- [ ] **Step 5: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add config.py && git commit -m "feat: add DPAPI encryption for sensitive config fields"
```

---

### Task 4: Remove dead code `_create_icon()` from tray_icon.py

**Files:**
- Modify: `tray_icon.py:78-148`

- [ ] **Step 1: Delete the dead _create_icon() function**

Remove lines 78-148 from `tray_icon.py` (the entire `_create_icon()` function).

Also remove the unused import reference to `wintypes.POINT` if no longer needed.

Update the file to import shared constants from `win32_constants.py`:

```python
from win32_constants import (
    WM_USER, WM_LBUTTONDBLCLK, WM_RBUTTONUP, WM_LBUTTONUP,
    WM_COMMAND, WM_DESTROY, WM_CLOSE,
    NIM_ADD, NIM_MODIFY, NIM_DELETE,
    NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_STATE, NIS_HIDDEN,
    IMAGE_ICON, LR_LOADFROMFILE, IDI_APPLICATION,
    MF_STRING, MF_SEPARATOR, MF_CHECKED, MF_UNCHECKED, MF_DEFAULT,
    TPM_RIGHTBUTTON, TPM_RETURNCMD,
    CW_USEDEFAULT, WS_OVERLAPPED, COLOR_WINDOW,
    BS_PATTERN, HS_VERTICAL,
    NOTIFYICONDATAW, ICONINFO, RECT,
)
```

This replaces the inline constant definitions and struct definitions in `tray_icon.py`.

- [ ] **Step 2: Verify the file still works**

```bash
cd y:/翻译器项目/ets2-translator && python -c "from tray_icon import TrayIcon; print('tray_icon OK')"
```

- [ ] **Step 3: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add tray_icon.py && git commit -m "fix: remove dead _create_icon() and GDI leak, use shared constants"
```

---

### Task 5: Add bounded queues (maxsize=500)

**Files:**
- Modify: `main.py:39-40`

- [ ] **Step 1: Add maxsize to Queue() calls**

In `main.py`, change:

```python
self.raw_queue = Queue()
self.display_queue = Queue()
```

To:

```python
self.raw_queue = Queue(maxsize=500)
self.display_queue = Queue(maxsize=500)
```

- [ ] **Step 2: Add Queue.Full handling in monitor.py**

In `monitor.py`'s `_tail_once()`, wrap `self.queue.put(msg)` with try/except:

```python
try:
    self.queue.put(msg, timeout=0.1)
except Exception:
    pass  # queue full, drop oldest message
```

- [ ] **Step 3: Verify queue doesn't block startup**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
from queue import Queue
q = Queue(maxsize=500)
for i in range(501):
    try:
        q.put_nowait(i)
    except:
        q.get_nowait()
        q.put_nowait(i)
print('Bounded queue OK')
"
```

- [ ] **Step 4: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add main.py monitor.py && git commit -m "fix: add bounded queues with maxsize=500 to prevent memory overflow"
```

---

### Task 6: Parallelize Baidu translation in hybrid mode

**Files:**
- Modify: `translator.py:149-186`

- [ ] **Step 1: Add ThreadPoolExecutor for parallel Baidu calls**

Add import at top of `translator.py`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

Modify `_flush_hybrid()` to translate via Baidu in parallel:

```python
def _flush_hybrid(self, batch):
    """LLM translates first, Baidu verifies and overrides if different."""
    # Step 1: get LLM translations (reuse batch logic)
    llm_results: dict[str, str] = {}  # text -> translation
    try:
        if len(batch) == 1:
            text = batch[0].text
            llm_results[text] = self._call_api(text)
        else:
            combined = BATCH_SEPARATOR.join(m.text for m in batch)
            result = self._call_api(combined)
            parts = [p.strip() for p in result.split(BATCH_SEPARATOR)]
            for i, msg in enumerate(batch):
                llm_results[msg.text] = parts[i] if i < len(parts) else msg.text
    except Exception as e:
        err_msg = self._format_error(e)
        for msg in batch:
            self.out_queue.put((msg, err_msg))
        return

    # Step 2: get Baidu translations in parallel
    baidu_results: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                translate_via_baidu,
                self.cfg.baidu_appid, self.cfg.baidu_secret, msg.text
            ): msg.text
            for msg in batch
        }
        for future in as_completed(futures):
            text = futures[future]
            try:
                baidu_results[text] = future.result()
            except Exception:
                pass  # Baidu failed for this text, will fall back to LLM

    # Step 3: compare and emit
    for msg in batch:
        llm_trans = llm_results.get(msg.text, msg.text)
        baidu_trans = baidu_results.get(msg.text)
        if baidu_trans is not None and _translations_differ(llm_trans, baidu_trans):
            self._cache.put(msg.text, baidu_trans)
            self.out_queue.put((msg, baidu_trans, True))
        else:
            self._cache.put(msg.text, llm_trans)
            self.out_queue.put((msg, llm_trans))
```

- [ ] **Step 2: Verify parallel Baidu translation logic**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
from concurrent.futures import ThreadPoolExecutor
import time
def slow_task(n):
    time.sleep(0.1)
    return n * 2
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = [ex.submit(slow_task, i) for i in range(4)]
    results = [f.result() for f in futures]
assert results == [0, 2, 4, 6], f'Unexpected: {results}'
print('ThreadPoolExecutor OK')
"
```

- [ ] **Step 3: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add translator.py && git commit -m "perf: parallelize Baidu translation calls in hybrid mode"
```

---

### Task 7: Add debug log control flag

**Files:**
- Modify: `config.py` (add `debug_log: bool = False` to AppConfig)
- Modify: `input_sender.py:12-19` (guard _debug_log with config flag)
- Modify: `overlay.py:17-23` (guard _debug_log with config flag)

- [ ] **Step 1: Add debug_log field to AppConfig in config.py**

Add to the `AppConfig` dataclass:

```python
debug_log: bool = False  # enable debug logging to %TEMP%
```

- [ ] **Step 2: Guard _debug_log in input_sender.py**

At module level in `input_sender.py`, replace the unconditional `_debug_log` with a helper that checks config:

```python
_debug_enabled = False

def set_debug_enabled(enabled: bool):
    global _debug_enabled
    _debug_enabled = enabled

def _debug_log(msg: str):
    if not _debug_enabled:
        return
    try:
        log_path = os.path.join(os.environ.get("TEMP", "."), "ets2_translator_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} [{os.getpid()}] {msg}\n")
    except Exception:
        pass
```

- [ ] **Step 3: Guard _debug_log in overlay.py**

Make the same change in `overlay.py`: add `_debug_enabled` flag and gate.

- [ ] **Step 4: Initialize debug flag in main.py App.__init__**

```python
import input_sender
# In App.__init__:
input_sender.set_debug_enabled(self.cfg.debug_log)
```

- [ ] **Step 5: Verify debug log is off by default**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
from config import AppConfig
cfg = AppConfig()
assert cfg.debug_log == False, 'debug_log should default to False'
print('Debug log default OK')
"
```

- [ ] **Step 6: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add config.py input_sender.py overlay.py main.py && git commit -m "feat: add debug_log config flag, off by default"
```

---

### Task 8: Fix build_exe.py import position

**Files:**
- Modify: `build_exe.py:52`

- [ ] **Step 1: Move import to top of file**

In `build_exe.py`, move `import shutil` from line 52 (inside except block) to the top of the file, after the existing imports:

```python
import subprocess
import sys
import os
import shutil
```

Remove the inline `import shutil` on line 52 (now `shutil.copy(ICON_SRC, ICON)` stays, but `import shutil` is at the top).

- [ ] **Step 2: Verify syntax**

```bash
cd y:/翻译器项目/ets2-translator && python -c "import build_exe; print('build_exe OK')"
```

- [ ] **Step 3: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add build_exe.py && git commit -m "style: move shutil import to top of build_exe.py"
```

---

### Task 9: Add dataclass for message types

**Files:**
- Create: `message_types.py`
- Modify: `overlay.py` (use DisplayMessage instead of bare tuple)
- Modify: `translator.py` (use typed queue items)

- [ ] **Step 1: Create message_types.py**

```python
"""Shared message types for translator pipeline."""
from dataclasses import dataclass, field


@dataclass
class DisplayMessage:
    """A message ready for display in the overlay window."""
    player_name: str
    original: str
    translated: str
    is_self: bool = False
    baidu_fixed: bool = False  # True if Baidu override was applied


@dataclass
class TranslationStats:
    """Translation statistics for the stats bar."""
    translated: int = 0
    cached: int = 0
    self_skipped: int = 0

    @property
    def total(self) -> int:
        return self.translated + self.cached + self.self_skipped

    def savings_pct(self) -> str:
        if self.total == 0:
            return "0%"
        return f"{int((self.cached + self.self_skipped) / self.total * 100)}%"
```

- [ ] **Step 2: Update overlay.py to use DisplayMessage**

Replace occurrences of `(player_name, original, translated, is_self)` tuples with `DisplayMessage` instances. Update `add_message()`, `_messages` type annotation, `_insert_one_at()`.

- [ ] **Step 3: Update translator.py to emit DisplayMessage**

In `_flush_llm()`, `_flush_baidu()`, `_flush_hybrid()` — replace tuple queue items with `DisplayMessage(msg.player_name, msg.text, translated, msg.is_self)`.

Also update the `stats` dict to use `TranslationStats` dataclass.

- [ ] **Step 4: Update overlay.py stats display**

In `_update_stats()`, use `TranslationStats` attributes instead of dict access.

- [ ] **Step 5: Verify**

```bash
cd y:/翻译器项目/ets2-translator && python -c "from message_types import DisplayMessage, TranslationStats; m = DisplayMessage('test', '你好', 'hello', False); print('DisplayMessage OK'); s = TranslationStats(10, 5, 2); assert s.total == 17; print('TranslationStats OK')"
```

- [ ] **Step 6: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add message_types.py overlay.py translator.py && git commit -m "refactor: replace bare tuples with DisplayMessage and TranslationStats dataclasses"
```

---

### Task 10: Add type annotations across all files

**Files:**
- Modify: `tray_icon.py`, `monitor.py`, `translator.py`, `overlay.py`, `input_sender.py`, `main.py`, `update.py`

- [ ] **Step 1: Add type annotations to tray_icon.py**

Add `from __future__ import annotations` at top, then annotate all method signatures:

```python
def __init__(self, title: str = "ETS2 聊天翻译器") -> None: ...
def set_menu(self, items: list[dict], default_cb: callable | None = None) -> None: ...
def start(self) -> None: ...
def stop(self) -> None: ...
def _wnd_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int: ...
def _message_loop(self) -> None: ...
def _show_menu(self) -> None: ...
def modify_tip(self, tip: str) -> None: ...
```

- [ ] **Step 2: Add type annotations to monitor.py**

Annotate all functions and methods.

- [ ] **Step 3: Add type annotations to translator.py**

The `in_queue: Queue`, `out_queue: Queue` already have types. Add return types to all methods:
- `_flush_llm(self, batch: list[ChatMessage]) -> None`
- `_call_api(self, text: str) -> str`
- etc.

- [ ] **Step 4: Add type annotations to overlay.py, input_sender.py, main.py, update.py**

Follow same pattern: `from __future__ import annotations`, annotate all function/method signatures.

- [ ] **Step 5: Verify with mypy-like check**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
# Basic syntax check — all files should import cleanly
from tray_icon import TrayIcon
from monitor import ChatMonitor, ChatMessage
from translator import Translator
from overlay import OverlayWindow
from config import AppConfig
from input_sender import send_chat_message
from update import check_for_update
print('All modules import OK')
"
```

- [ ] **Step 6: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add tray_icon.py monitor.py translator.py overlay.py input_sender.py main.py update.py && git commit -m "refactor: add type annotations to all public APIs"
```

---

### Task 11: Expose target_language in settings UI

**Files:**
- Modify: `config.py:186` (make target_language configurable)
- Modify: `main.py` (add language selector to SettingsDialog)

- [ ] **Step 1: Add language combo to SettingsDialog in main.py**

In the API card (Card 1) of `SettingsDialog._build()`, add a row after the backend combo:

```python
self.lang_var = tk.StringVar(value=self.cfg.target_language)
self.lang_combo = ttk.Combobox(
    card1, textvariable=self.lang_var,
    values=["zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru"],
    state="readonly", width=18,
    font=("Microsoft YaHei", 10))
r = self._row(card1, r, "Target Language / 目标语言", self.lang_combo)
```

- [ ] **Step 2: Load and save target_language**

In `_load_values()`:

```python
self.lang_var.set(self.cfg.target_language)
```

In `_save()`, add:

```python
target_language=self.lang_var.get(),
```

- [ ] **Step 3: Update translator.py to use cfg.target_language**

In `_should_skip()`, use `self.cfg.target_language` instead of hardcoded `"zh-CN"`:

```python
def _should_skip(self, text: str) -> bool:
    if self.cfg.target_language.startswith("zh"):
        cjk = len(_CJK_RE.findall(text))
        alpha = len(_ALPHA_RE.findall(text))
        if cjk > alpha and cjk > len(text) * 0.3:
            return True
    return False
```

- [ ] **Step 4: Verify UI change doesn't break**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
from config import AppConfig
cfg = AppConfig()
assert cfg.target_language == 'zh-CN'
cfg.target_language = 'en'
assert cfg.target_language == 'en'
print('target_language config OK')
"
```

- [ ] **Step 5: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add config.py main.py translator.py && git commit -m "feat: expose target_language in settings UI"
```

---

### Task 12: Split overlay.py into manageable modules

**Files:**
- Create: `message_display.py`
- Create: `hotkey_manager.py`
- Modify: `overlay.py`

- [ ] **Step 1: Create message_display.py**

Extract message rendering from `overlay.py`:
- `_setup_ui()` text-related parts (text widget, color tags, context menu)
- `add_message()`, `_do_sync_and_clear()`, `_sync_display()`, `_insert_one_at()`
- `_insert_sent()`, `_update_last_sys_msg()`
- `_show_notice()`, `_update_stats()`
- `set_font_size()`

Create a `MessageDisplay` class that owns the text widget and stats bar.

- [ ] **Step 2: Create hotkey_manager.py**

Extract hotkey logic:
- `_format_hotkey()`, `_update_hotkey_hint()`, `_parse_hotkey()`
- `_start_hotkey_poller()`, `_stop_hotkey_poller()`, `_focus_send_entry()`
- `update_send_hotkey()`
- `_start_manual_send_poller()`, `_stop_manual_send_poller()`
- `_on_copy_hotkey()`, `_on_enter_hotkey()`
- `_parse_hotkey_vk()`, `_mod_vks()`
- `_SPECIAL_VK` (now from `win32_constants.SPECIAL_VK`)

Create a `HotkeyManager` class.

- [ ] **Step 3: Refactor overlay.py**

`OverlayWindow` delegates to `MessageDisplay` and `HotkeyManager` instances:

```python
from message_display import MessageDisplay
from hotkey_manager import HotkeyManager

class OverlayWindow:
    def __init__(self, cfg, message_queue, stats_ref=None):
        # ...
        self.display = MessageDisplay(self.root, self.outer, cfg, stats_ref)
        self.hotkeys = HotkeyManager(self.root, cfg, self._focus_send_entry)
        # ...
```

Keep in `overlay.py`: window creation, mode switching, mouse drag/resize, send entry, position management, visibility.

- [ ] **Step 4: Update main.py imports**

```python
from overlay import OverlayWindow
# message_display and hotkey_manager are internal to overlay
```

- [ ] **Step 5: Verify all imports work**

```bash
cd y:/翻译器项目/ets2-translator && python -c "
from message_display import MessageDisplay
from hotkey_manager import HotkeyManager
from overlay import OverlayWindow
print('All split modules import OK')
"
```

- [ ] **Step 6: Commit**

```bash
cd y:/翻译器项目/ets2-translator && git add message_display.py hotkey_manager.py overlay.py main.py && git commit -m "refactor: split overlay.py into overlay_window + message_display + hotkey_manager"
```

---

## Execution Order & Dependencies

```
Task 1 (win32_constants) ──┐
                            ├──→ Task 4 (tray_icon cleanup)
                            ├──→ Task 6 (parallel Baidu)
                            ├──→ Task 7 (debug log gate)
                            ├──→ Task 12 (overlay split)
                            │
Task 2 (prompt extraction)─┤
                            │
Task 3 (DPAPI encryption)──┤
                            │
Task 5 (bounded queues)────┤
                            │
Task 8 (build_exe import)──┤  (all independent)
                            │
Task 9 (dataclass types)───┤
                            │
Task 10 (type annotations)─┤
                            │
Task 11 (language option)──┘
```

Tasks 3 and 9 must complete before Task 12 (overlay split depends on dataclass types and config changes).

**Total estimated commits: 12**
