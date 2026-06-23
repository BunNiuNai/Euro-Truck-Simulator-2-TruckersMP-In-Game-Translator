# Auto-Send with Chat Log Confirmation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manual compose→send flow with automatic send-to-game + chat log confirmation, matching Seven-TMP behavior.

**Architecture:** New `compose_sender.py` module contains `ComposeSender` class handling validation, clipboard save/restore, send execution, and chat log confirmation via **independent file tailing** (reads the chat log file directly — does NOT consume from the shared `raw_queue`, avoiding message theft from the translator). `overlay.py` calls it from a background thread to avoid blocking the Tkinter event loop; UI updates go through `root.after()`.

**Tech Stack:** Python 3.10+, Tkinter, Win32 API (ctypes)

**Key design decision — file-based confirmation:** The `raw_queue` is shared between monitor and translator. If ComposeSender consumed from it, messages would be stolen from the translator. Instead, `_wait_confirmation()` opens the chat log file directly, seeks to end, and polls for new lines — completely independent of the translation pipeline.

---

## File Map

```
compose_sender.py     ← CREATE  (~140 lines)  ComposeSender class
overlay.py            ← MODIFY (~30 added, ~60 removed)
hotkey_manager.py     ← MODIFY (~50 removed)
main.py               ← NO CHANGE
```

---

### Task 1: Write tests for compose_sender.py

**Files:**
- Create: `y:\翻译器项目\ets2-translator\test_compose_sender.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for compose_sender module."""
import os
import tempfile
import time
import pytest

from compose_sender import ComposeSender, SendResult, _normalize, _is_mostly_chinese


class TestNormalize:
    def test_trim_whitespace(self):
        assert _normalize("  hello  ") == "hello"

    def test_collapse_inner_whitespace(self):
        assert _normalize("hello   world") == "hello world"

    def test_newlines_and_tabs(self):
        assert _normalize("hello\t\nworld") == "hello world"

    def test_empty_string(self):
        assert _normalize("   ") == ""

    def test_chinese_text_preserved(self):
        assert _normalize("你好  世界") == "你好 世界"


class TestIsMostlyChinese:
    def test_pure_chinese(self):
        assert _is_mostly_chinese("你好世界这是一个测试") is True

    def test_mixed_mostly_chinese(self):
        assert _is_mostly_chinese("你好世界ab测试cd") is True

    def test_pure_english(self):
        assert _is_mostly_chinese("hello world this is a test") is False

    def test_mixed_mostly_english(self):
        assert _is_mostly_chinese("hello 你好 world test") is False

    def test_empty_string(self):
        assert _is_mostly_chinese("") is False


class FakeConfig:
    chat_hotkey = "y"
    player_name = "TestPlayer"


class TestComposeSenderValidate:
    def setup_method(self):
        self.sender = ComposeSender(FakeConfig())

    def test_empty_english(self):
        assert self.sender.validate("你好", "") is False

    def test_same_as_chinese(self):
        assert self.sender.validate("hello", "hello") is False

    def test_same_with_whitespace(self):
        assert self.sender.validate("  hello  ", "hello") is False

    def test_still_mostly_chinese(self):
        assert self.sender.validate("你好世界翻译失败", "你好世界翻译失败") is False

    def test_valid_translation(self):
        assert self.sender.validate("你好世界", "hello world") is True

    def test_valid_with_spaces(self):
        assert self.sender.validate("  你好  ", "hello") is True


class TestComposeSenderWaitConfirmation:
    """Test _wait_confirmation using a real temp file (simulates chat log)."""

    def setup_method(self):
        self.sender = ComposeSender(FakeConfig())
        self.tmpdir = tempfile.mkdtemp(prefix="ets2_test_")
        # Patch find_latest_log to return our temp file
        self.log_path = os.path.join(self.tmpdir, "chat_2026_06_23_log.txt")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("")  # empty file

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _append_line(self, channel, time_str, player, text):
        """Append a TruckersMP-format chat line to the test log."""
        line = f"[{channel}] [{time_str}] {player} (A 123): {text}\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def test_match_found(self):
        # Start confirmation on background thread, then write matching line
        import threading
        result_holder = []

        def do_confirm():
            result_holder.append(
                self.sender._wait_confirmation("hello world", timeout=2.0, log_path=self.log_path)
            )

        t = threading.Thread(target=do_confirm, daemon=True)
        t.start()
        time.sleep(0.15)
        self._append_line("Global", "12:00:00", "OtherPlayer", "hello world")
        t.join(timeout=3.0)
        assert result_holder[0] is True

    def test_no_match_timeout(self):
        result = self.sender._wait_confirmation(
            "unique text nobody typed", timeout=0.3, log_path=self.log_path
        )
        assert result is False

    def test_skips_self_player(self):
        """Messages from the configured player_name should be skipped."""
        import threading
        result_holder = []

        def do_confirm():
            result_holder.append(
                self.sender._wait_confirmation("hello world", timeout=2.0, log_path=self.log_path)
            )

        t = threading.Thread(target=do_confirm, daemon=True)
        t.start()
        time.sleep(0.15)
        # Write self-message first — should be skipped
        self._append_line("Global", "12:00:00", "TestPlayer", "hello world")
        time.sleep(0.2)
        # Then write non-self message — should match
        self._append_line("Global", "12:00:01", "OtherPlayer", "hello world")
        t.join(timeout=3.0)
        assert result_holder[0] is True

    def test_normalized_match(self):
        """Whitespace differences should still match."""
        import threading
        result_holder = []

        def do_confirm():
            result_holder.append(
                self.sender._wait_confirmation("  hello   world  ", timeout=2.0, log_path=self.log_path)
            )

        t = threading.Thread(target=do_confirm, daemon=True)
        t.start()
        time.sleep(0.15)
        self._append_line("Global", "12:00:00", "OtherPlayer", "hello world")
        t.join(timeout=3.0)
        assert result_holder[0] is True

    def test_only_reads_new_lines(self):
        """Pre-existing lines before _wait_confirmation starts should be ignored."""
        # Write a line BEFORE confirmation starts
        self._append_line("Global", "11:00:00", "OldPlayer", "hello world")
        # Now start confirmation for a different text — should NOT match the old line
        result = self.sender._wait_confirmation(
            "completely different text", timeout=0.5, log_path=self.log_path
        )
        assert result is False


class TestSendResult:
    def test_enum_values(self):
        assert SendResult.OK_CONFIRMED == "OK_CONFIRMED"
        assert SendResult.OK_UNCONFIRMED == "OK_UNCONFIRMED"
        assert SendResult.FAIL_SEND == "FAIL_SEND"
        assert SendResult.FAIL_TRANSLATION == "FAIL_TRANSLATION"
        assert SendResult.BUSY == "BUSY"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "y:/翻译器项目/ets2-translator" && python -m pytest test_compose_sender.py -v
```

Expected: All tests FAIL — `compose_sender` module does not exist yet.

- [ ] **Step 3: Commit**

```bash
git add test_compose_sender.py
git commit -m "test: add compose_sender unit tests (red phase)"
```

---

### Task 2: Create compose_sender.py module

**Files:**
- Create: `y:\翻译器项目\ets2-translator\compose_sender.py`

- [ ] **Step 1: Write the module**

```python
"""
Compose sender: validate translation, auto-send to game chat,
confirm delivery via chat log tailing, restore clipboard.

Confirmation reads the chat log FILE directly (does NOT consume from
the shared raw_queue) to avoid stealing messages from the translator.
"""
import os
import re
import threading
import time
from enum import Enum

from config import AppConfig
from input_sender import send_chat_message, clipboard_get, clipboard_set
from logger import get_logger

_CJK_RE = re.compile(r"[一-鿿]")


class SendResult(str, Enum):
    OK_CONFIRMED = "OK_CONFIRMED"
    OK_UNCONFIRMED = "OK_UNCONFIRMED"
    FAIL_SEND = "FAIL_SEND"
    FAIL_TRANSLATION = "FAIL_TRANSLATION"
    BUSY = "BUSY"


def _normalize(text: str) -> str:
    """Collapse all whitespace to single space, strip."""
    return re.sub(r"\s+", " ", text).strip()


def _is_mostly_chinese(text: str) -> bool:
    """Return True if >30% of characters are CJK (U+4E00-U+9FFF)."""
    if not text:
        return False
    cjk = sum(1 for c in text if _CJK_RE.match(c))
    return (cjk / len(text)) > 0.3


class ComposeSender:
    """Handles the full compose→translate→send→confirm pipeline.

    Uses file-based chat log confirmation — does NOT touch the
    monitor→translator message queue, so no messages are stolen.
    """

    __slots__ = ("cfg", "_busy_lock")

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._busy_lock = threading.Lock()

    # ── public API ──

    def validate(self, chinese: str, english: str) -> bool:
        """Check that the translation is usable:
        - not empty
        - not identical to the input
        - not still mostly Chinese characters (>30%)
        """
        eng = (english or "").strip()
        chn = (chinese or "").strip()
        if not eng:
            return False
        if eng == chn:
            return False
        if _is_mostly_chinese(eng):
            return False
        return True

    def execute_send(self, english: str) -> SendResult:
        """Send to game and wait for chat log confirmation.
        Must be called from a background thread (blocks for up to ~2.8s).
        Thread-safe: only one send at a time (BUSY if concurrent).
        """
        if not self._busy_lock.acquire(blocking=False):
            return SendResult.BUSY

        try:
            return self._do_execute(english)
        finally:
            self._busy_lock.release()

    # ── internal ──

    def _do_execute(self, english: str) -> SendResult:
        old_clip = clipboard_get()

        err = send_chat_message(english, self.cfg.chat_hotkey)
        if err:
            clipboard_set(old_clip)
            log = get_logger()
            if log:
                log.error("SEND", f"发送失败: {err}")
            return SendResult.FAIL_SEND

        confirmed = self._wait_confirmation(english, timeout=2.5)
        clipboard_set(old_clip)

        log = get_logger()
        if log:
            status = "确认成功" if confirmed else "确认超时"
            log.info("SEND", f"发送完成: {status} | {english[:50]}")

        return SendResult.OK_CONFIRMED if confirmed else SendResult.OK_UNCONFIRMED

    def _wait_confirmation(self, text: str, timeout: float = 2.5,
                           log_path: str | None = None) -> bool:
        """Read chat log file from current position, looking for our text.
        Only reads NEW lines written after this method starts.
        Skips lines from the configured player_name (self).

        Args:
            text: The normalized text to search for.
            timeout: Maximum seconds to wait.
            log_path: Override path (for testing). If None, auto-detect.
        """
        normalized = _normalize(text)
        if not normalized:
            return False

        # Resolve log path
        if log_path is None:
            from monitor import find_latest_log
            log_path = find_latest_log()
        if not log_path or not os.path.isfile(log_path):
            return False

        player_name = (self.cfg.player_name or "").strip()

        # Compile the chat line regex (same pattern as monitor.py)
        _CHAT_RE = re.compile(
            r"^\[(?P<channel>.+?)\]\s+"
            r"\[(?P<time>\d{2}:\d{2}:\d{2})\]\s+"
            r"(?P<player>.+?)\s+\([A-Z]?\s*\d+\):\s+"
            r"(?P<text>.+)$"
        )

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                # Seek to end — only read lines written after this point
                f.seek(0, 2)

                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    line = f.readline()
                    if line:
                        line = line.strip()
                        if not line:
                            continue
                        m = _CHAT_RE.match(line)
                        if m:
                            msg_text = m.group("text")
                            msg_player = m.group("player")
                            if _normalize(msg_text) == normalized:
                                if player_name and msg_player == player_name:
                                    continue  # skip self
                                return True
                    else:
                        time.sleep(0.08)

        except OSError:
            return False

        return False
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd "y:/翻译器项目/ets2-translator" && python -m pytest test_compose_sender.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add compose_sender.py
git commit -m "feat: add ComposeSender with file-based chat log confirmation"
```

---

### Task 3: Modify overlay.py — integrate auto-send

**Files:**
- Modify: `y:\翻译器项目\ets2-translator\overlay.py`

- [ ] **Step 1: Add `import time` to top of file**

At line 11 (after `import threading`):

```python
import time
```

- [ ] **Step 2: Replace `_on_translate_done` with auto-send flow**

Delete the current `_on_translate_done` (lines 811-822) and replace with:

```python
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
```

- [ ] **Step 3: Remove manual send poller methods**

Delete these methods entirely:
- `_start_manual_send_poller` (~lines 858-896)
- `_stop_manual_send_poller` (~lines 898-899)
- `_on_copy_hotkey` (~lines 901-907)
- `_on_enter_hotkey` (~lines 909-917)

- [ ] **Step 4: Commit**

```bash
git add overlay.py
git commit -m "feat: replace manual send with auto-send + confirmation in overlay"
```

---

### Task 4: Clean up hotkey_manager.py

**Files:**
- Modify: `y:\翻译器项目\ets2-translator\hotkey_manager.py`

- [ ] **Step 1: Remove manual send methods**

Delete the entire "Manual send hotkey poller" section — the class attribute `_manual_poller_active`, methods `start_manual_send`, `stop_manual_send`, `_on_copy`, `_on_enter`, and the `on_copy`/`on_enter` callback stubs. This is approximately lines 196-248.

- [ ] **Step 2: Verify no remaining references**

```bash
cd "y:/翻译器项目/ets2-translator" && grep -rn "start_manual_send\|stop_manual_send\|_manual_poller" *.py
```

Expected: No output (all references removed).

- [ ] **Step 3: Commit**

```bash
git add hotkey_manager.py
git commit -m "refactor: remove manual send poller from hotkey_manager"
```

---

### Task 5: Verify — run tests and check imports

**Files:** None

- [ ] **Step 1: Run all unit tests**

```bash
cd "y:/翻译器项目/ets2-translator" && python -m pytest test_compose_sender.py test_logger.py test_provider_config.py -v
```

Expected: All tests PASS.

- [ ] **Step 2: Verify compose_sender imports cleanly**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from compose_sender import ComposeSender, SendResult, _normalize, _is_mostly_chinese
print('Import OK')
print('SendResult:', [r.value for r in SendResult])
print('_normalize test:', repr(_normalize('  hello   world  ')))
print('_is_mostly_chinese test:', _is_mostly_chinese('你好世界test'))
"
```

Expected output:
```
Import OK
SendResult: ['OK_CONFIRMED', 'OK_UNCONFIRMED', 'FAIL_SEND', 'FAIL_TRANSLATION', 'BUSY']
_normalize test: 'hello world'
_is_mostly_chinese test: True
```

- [ ] **Step 3: Verify overlay imports without errors**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
import overlay
print('Overlay module imported OK')
# Check that removed methods are truly gone
assert not hasattr(overlay.OverlayWindow, '_start_manual_send_poller'), 'orphan method!'
assert not hasattr(overlay.OverlayWindow, '_on_copy_hotkey'), 'orphan method!'
print('Manual send methods correctly removed')
"
```

Expected:
```
Overlay module imported OK
Manual send methods correctly removed
```

- [ ] **Step 4: Commit final state**

```bash
git add -A
git diff --cached --stat
git commit -m "verify: all tests pass after auto-send integration"
```
