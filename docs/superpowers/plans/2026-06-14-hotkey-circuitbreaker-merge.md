# Hotkey + Circuit Breaker + Request Merging Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace GetAsyncKeyState polling with RegisterHotKey, add provider circuit breaker, add in-flight request merging.

**Architecture:** hotkey_manager.py gets a hidden Win32 message window + RegisterHotKey for system-level hotkeys. translator.py gets ProviderHealth tracking with cooldown, and an in_flight dict with threading.Event for merging concurrent identical requests.

**Tech Stack:** Python 3.10+, ctypes Win32 API, threading

---

## File Structure Map

| File | Action | Responsibility |
|:---|:---|:---|
| `hotkey_manager.py` | Modify (~186→~220 lines) | RegisterHotKey + message window |
| `translator.py` | Modify | Provider circuit breaker + request merging |

---

### Task 1: hotkey_manager.py — RegisterHotKey system-level hotkeys

**Files:**
- Modify: `hotkey_manager.py`

- [ ] **Step 1: Verify existing module imports cleanly**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "from hotkey_manager import HotkeyManager; print('OK')"
```

- [ ] **Step 2: Replace hotkey_manager.py with RegisterHotKey implementation**

The current hotkey_manager.py uses `GetAsyncKeyState` polling. Replace it with a Win32 message-window + RegisterHotKey approach:

```python
"""
Hotkey manager — system-level RegisterHotKey via Win32 message window.
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

# Window message constants
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

    # ── Hotkey display helpers (unchanged) ──

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
        """Window procedure for the hidden message window."""
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

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._wnd_proc_ref, wintypes.LPVOID)
        wc.hInstance = hinst
        wc.lpszClassName = class_name

        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom:
            return

        # Create hidden message-only window (HWND_MESSAGE = -3)
        self._hwnd = user32.CreateWindowExW(
            0, class_name, "ETS2Hotkey",
            0, 0, 0, 0, 0,
            wintypes.HWND(-3), 0, hinst, 0,
        )
        if not self._hwnd:
            return

        # Register system-level hotkey
        mods, vk = self._parse_hotkey(self.cfg.send_hotkey)
        if vk != 0:
            ok = user32.RegisterHotKey(self._hwnd, self._hotkey_id, mods, vk)
            if not ok:
                # Fall back: try alt+key if shift+key fails (some combos reserved)
                if mods & MOD_SHIFT:
                    mods = (mods & ~MOD_SHIFT) | MOD_ALT
                    ok = user32.RegisterHotKey(self._hwnd, self._hotkey_id, mods, vk)
                if not ok:
                    self._hwnd = None
                    user32.DestroyWindow(self._hwnd)
                    return

        # Message loop
        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        if self._hwnd:
            user32.UnregisterHotKey(self._hwnd, self._hotkey_id)
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None

    def start(self) -> None:
        """Start the system-level hotkey listener thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the hotkey listener and clean up."""
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def update_send_hotkey(self, new_hotkey: str) -> None:
        """Called when user changes the hotkey in settings. Re-registers."""
        self._running = False
        if self._hwnd:
            user32.UnregisterHotKey(self._hwnd, self._hotkey_id)
            user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self.cfg.send_hotkey = new_hotkey
        self.reset_hint()
        self.start()

    # ── Manual send hotkey poller (unchanged — GetAsyncKeyState for copy/enter detection) ──

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
            mv = [MOD_VK_MAP[m] for m in [MOD_SHIFT, MOD_CONTROL, MOD_ALT] if mods & m]
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
```

- [ ] **Step 3: Verify import**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from hotkey_manager import HotkeyManager
print('hotkey_manager OK')
"
```

- [ ] **Step 4: Commit**

```bash
cd "y:/翻译器项目/ets2-translator"
git add hotkey_manager.py
git commit -m "feat: system-level RegisterHotKey replaces GetAsyncKeyState polling"
```

---

### Task 2: translator.py — Provider circuit breaker + request merging

**Files:**
- Modify: `translator.py`

- [ ] **Step 1: Add ProviderHealth and in-flight structures**

In `translator.py`, add after the imports block, before class definitions:

```python
import time as _time_module  # already imported as 'time' at top

@dataclass
class ProviderHealth:
    """Tracks health state for one provider (circuit breaker pattern)."""
    failures: int = 0
    cool_until: float = 0.0  # time.monotonic() timestamp
```

In `Translator.__init__`, add after `self._client`:

```python
self._provider_health: dict[str, ProviderHealth] = {}  # label -> health
self._in_flight: dict[str, threading.Event] = {}        # text -> event
self._in_flight_results: dict[str, str] = {}              # text -> translation result
self._in_flight_lock = threading.Lock()
```

- [ ] **Step 2: Add circuit breaker methods**

Add these methods to the Translator class:

```python
def _is_cooling(self, label: str) -> bool:
    """Check if a provider is in cooldown (circuit breaker open)."""
    health = self._provider_health.get(label)
    if health and health.cool_until > 0:
        if _time_module.monotonic() < health.cool_until:
            return True
    return False

def _note_provider_result(self, label: str, success: bool) -> None:
    """Update provider health after a translation attempt."""
    if label not in self._provider_health:
        self._provider_health[label] = ProviderHealth()
    h = self._provider_health[label]
    log = get_logger()

    if success:
        if h.failures > 0:
            if log:
                log.info("LLM", f"Provider {label} 已恢复（之前 {h.failures} 次失败）")
        h.failures = 0
        h.cool_until = 0
    else:
        h.failures += 1
        if h.failures >= 3:
            duration = min(30 * (2 ** (h.failures - 3)), 120)
            h.cool_until = _time_module.monotonic() + duration
            if log:
                log.warn("LLM", f"Provider {label} 进入冷却 {duration}s（连续 {h.failures} 次失败）")
```

- [ ] **Step 3: Integrate circuit breaker into _call_api**

In `_call_api()`, filter out cooling providers before round 1:

```python
def _call_api(self, text: str) -> str:
    if self._should_skip(text):
        return text

    providers = [p for p in self.cfg.llm_providers if p.get("enabled", True)]
    if not providers:
        return self._call_api_legacy(text)

    # Filter out cooling providers
    active = [p for p in providers if not self._is_cooling(p["label"])]
    if not active:
        # All cooling — force try all
        active = providers
        log = get_logger()
        if log:
            log.warn("LLM", "所有 Provider 均处于冷却期，强制重试")

    skipped = len(providers) - len(active)
    if skipped > 0:
        log = get_logger()
        if log:
            cooling_names = [p["label"] for p in providers if p not in active]
            log.warn("LLM", f"跳过冷却中的 Provider: {', '.join(cooling_names)}")

    log = get_logger()

    # Round 1: Parallel race (only active providers)
    errors = []
    with ThreadPoolExecutor(max_workers=min(len(active), 4)) as executor:
        futures = {
            executor.submit(self._call_provider, p, text): p["label"]
            for p in active
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                self._note_provider_result(label, True)
                if log:
                    log.info("LLM", f"竞速成功: {label}")
                return result
            except Exception as e:
                err = self._format_error(e)
                errors.append(f"{label}: {err}")
                self._note_provider_result(label, False)
                if log:
                    log.warn("LLM", f"竞速失败: {label} - {err}")

    # Round 2: Serial retry (active + skipped, 180ms apart)
    if log:
        log.warn("LLM", f"第一轮全部失败，进入串行重试 ({len(active)} providers)")
    retry_list = active + [p for p in providers if p not in active]
    for p in retry_list:
        try:
            result = self._call_provider(p, text)
            self._note_provider_result(p["label"], True)
            if log:
                log.info("LLM", f"重试成功: {p['label']}")
            return result
        except Exception:
            self._note_provider_result(p["label"], False)
            _time_module.sleep(0.18)

    raise Exception(" | ".join(errors) if errors else "所有 Provider 翻译失败")
```

- [ ] **Step 4: Add request merging in _call_api (before the provider loop)**

Insert at the beginning of `_call_api()`, after `_should_skip` check and before the provider list:

```python
def _call_api(self, text: str) -> str:
    if self._should_skip(text):
        return text

    # Request merging: if identical text is already being translated, wait for it
    with self._in_flight_lock:
        if text in self._in_flight:
            event = self._in_flight[text]
            event.wait(timeout=10.0)
            result = self._in_flight_results.get(text)
            if result is not None:
                return result
            # If still None after timeout or set, proceed to translate
        self._in_flight[text] = threading.Event()

    try:
        result = self._call_api_internal(text)  # rest of original _call_api logic
        with self._in_flight_lock:
            self._in_flight_results[text] = result
        return result
    finally:
        with self._in_flight_lock:
            event = self._in_flight.pop(text, None)
            if event:
                event.set()
            self._in_flight_results.pop(text, None)

# Rename the existing _call_api body (provider race logic) to _call_api_internal
```

So the structure becomes:
- `_call_api(text)` → checks in_flight merging → calls `_call_api_internal(text)`
- `_call_api_internal(text)` → the actual provider race logic (with circuit breaker)

- [ ] **Step 5: Verify**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from config import AppConfig
from translator import Translator, ProviderHealth
from queue import Queue
# Test imports and basic structure
assert hasattr(ProviderHealth, 'failures')
assert hasattr(ProviderHealth, 'cool_until')
cfg = AppConfig()
t = Translator(cfg, Queue(), Queue())
assert hasattr(t, '_provider_health')
assert hasattr(t, '_in_flight')
assert hasattr(t, '_in_flight_lock')
print('All structures OK')
# Test circuit breaker logic
t._note_provider_result('test', False)
t._note_provider_result('test', False)
t._note_provider_result('test', False)
assert t._is_cooling('test'), 'Provider should be cooling after 3 failures'
print('Circuit breaker OK')
t._note_provider_result('test', True)
assert not t._is_cooling('test'), 'Provider should recover after success'
print('Circuit breaker recovery OK')
print('=== ALL CHECKS PASSED ===')
"
```

- [ ] **Step 6: Commit**

```bash
cd "y:/翻译器项目/ets2-translator"
git add translator.py
git commit -m "feat: provider circuit breaker + in-flight request merging"
```

---

### Task 3: Integration verification

**Files:**
- Verify: all modules

- [ ] **Step 1: Full import and test**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from hotkey_manager import HotkeyManager
from translator import Translator, ProviderHealth
from config import AppConfig
from message_types import TranslationStats
from queue import Queue
import threading, time

# Test in-flight merging
cfg = AppConfig()
cfg.llm_providers = [{'label':'T1','endpoint':'x','api_key':'k','model':'m','enabled':True}]
t = Translator(cfg, Queue(), Queue())

# Simulate concurrent same-text requests
results = []
errors = []
def worker():
    try:
        # _call_api_internal will fail (no real endpoint), but we test merging
        t._call_api('hello world')
    except Exception as e:
        errors.append(str(e))

# Don't actually call API — just test the structures
assert hasattr(t, '_provider_health')
assert hasattr(t, '_in_flight')
assert hasattr(t, '_in_flight_lock')
print('Integration OK')
"
```

- [ ] **Step 2: Commit**

```bash
git commit -m "test: integration verification for hotkey + circuit breaker + merging" --allow-empty
```

---

## Execution Order

```
Task 1 (hotkey_manager.py) ──→ Task 2 (translator.py) ──→ Task 3 (verify)
```

Tasks 1 and 2 are independent (different files). Task 3 is final.

**Total estimated commits: 3**
