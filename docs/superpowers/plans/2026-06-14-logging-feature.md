# Logging Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add centralized logging to file and settings dialog without changing existing functionality.

**Architecture:** New `logger.py` module provides thread-safe file logging with rotation + in-memory buffer. All existing modules call `get_logger().info/warn/error()` at key events. SettingsDialog gets a 4th "日志" tab showing the buffer content.

**Tech Stack:** Python 3.10+, threading, tkinter, `os.startfile` for opening log folder.

---

## File Structure Map

| File | Action | Responsibility |
|:---|:---|:---|
| `logger.py` | **Create** | Central logger: file write, rotation, in-memory buffer, singleton |
| `test_logger.py` | **Create** | Verification script for logger module |
| `main.py` | Modify | Init logger in App, add log tab to SettingsDialog, system events |
| `monitor.py` | Modify | Log TMP events (dir status, file switch, parse errors) |
| `translator.py` | Modify | Log LLM/Baidu connectivity, errors, periodic stats |
| `overlay.py` | Modify | Log hotkey events |
| `update.py` | Modify | Log update check/download/install events |

---

### Task 1: Create logger.py module

**Files:**
- Create: `logger.py`
- Create: `test_logger.py`

- [ ] **Step 1: Write the verification script**

```python
# test_logger.py
"""Quick verification of logger module functionality."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import Logger

def test_basic_logging():
    """Write some log entries and verify they appear in file and buffer."""
    tmpdir = tempfile.mkdtemp(prefix="ets2_log_test_")
    log = Logger(log_dir=tmpdir, max_files=3, max_size=1024, buffer_size=10)

    log.info("SYS", "测试启动")
    log.warn("LLM", "测试警告")
    log.error("BDU", "测试错误")

    # Check buffer
    recent = log.get_recent()
    assert len(recent) == 3, f"Expected 3 entries, got {len(recent)}"
    assert "[INFO]" in recent[0]
    assert "[WARN]" in recent[1]
    assert "[ERROR]" in recent[2]
    assert "测试启动" in recent[0]
    print("PASS: buffer content")

    # Check file
    log_files = [f for f in os.listdir(tmpdir) if f.endswith('.log')]
    assert len(log_files) == 1, f"Expected 1 log file, got {len(log_files)}"
    with open(os.path.join(tmpdir, log_files[0]), 'r', encoding='utf-8') as f:
        content = f.read()
    assert "测试启动" in content
    assert "测试警告" in content
    assert "测试错误" in content
    print("PASS: file content")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("ALL TESTS PASSED")


def test_buffer_limit():
    """Verify buffer doesn't exceed max size."""
    tmpdir = tempfile.mkdtemp(prefix="ets2_log_test_")
    log = Logger(log_dir=tmpdir, max_files=3, max_size=1024 * 1024, buffer_size=5)

    for i in range(10):
        log.info("TST", f"消息 {i}")

    recent = log.get_recent()
    assert len(recent) == 5, f"Buffer should be 5, got {len(recent)}"
    assert "消息 9" in recent[-1]
    assert "消息 5" in recent[0]
    print("PASS: buffer limit")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_thread_safety():
    """Verify concurrent writes don't crash or corrupt."""
    import threading
    tmpdir = tempfile.mkdtemp(prefix="ets2_log_test_")
    log = Logger(log_dir=tmpdir, max_files=3, max_size=1024 * 1024, buffer_size=100)

    def writer(tag, count):
        for i in range(count):
            log.info(tag, f"线程消息 {i}")

    threads = [threading.Thread(target=writer, args=(f"T{i}", 50)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    recent = log.get_recent()
    assert len(recent) == 100, f"Buffer should be 100, got {len(recent)}"
    print("PASS: thread safety")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_get_log_dir():
    """Verify get_log_dir returns the correct path."""
    tmpdir = tempfile.mkdtemp(prefix="ets2_log_test_")
    log = Logger(log_dir=tmpdir)
    assert log.get_log_dir() == tmpdir
    print("PASS: get_log_dir")

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    test_basic_logging()
    test_buffer_limit()
    test_thread_safety()
    test_get_log_dir()
    print("\n=== ALL LOGGER TESTS PASSED ===")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "y:/翻译器项目/ets2-translator" && python test_logger.py
```

Expected: `ModuleNotFoundError: No module named 'logger'`

- [ ] **Step 3: Create logger.py**

```python
"""
Centralized logging for ETS2 Chat Translator.
Writes to Documents/ETS2 Translator/logs/ with auto-rotation.
Keeps an in-memory buffer for UI display.
Thread-safe.
"""
import os
import threading
from datetime import datetime


MAX_LOG_FILES = 7
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
BUFFER_SIZE = 500

_LEVEL_LABEL = {"INFO": "INFO ", "WARN": "WARN ", "ERROR": "ERROR"}


def _get_default_log_dir() -> str:
    """Get default log directory under config dir. Avoids circular import."""
    from config import CONFIG_DIR
    return os.path.join(CONFIG_DIR, "logs")


class Logger:
    """Thread-safe file logger with in-memory buffer and auto-rotation."""

    def __init__(self, log_dir: str | None = None, max_files: int = MAX_LOG_FILES,
                 max_size: int = MAX_FILE_SIZE, buffer_size: int = BUFFER_SIZE):
        self._log_dir = log_dir or _get_default_log_dir()
        self._max_files = max_files
        self._max_size = max_size
        self._buffer: list[str] = []
        self._buffer_size = buffer_size
        self._lock = threading.Lock()
        os.makedirs(self._log_dir, exist_ok=True)
        self._cleanup_old_logs()

    # ── file management ──

    def _current_log_path(self) -> str:
        return os.path.join(
            self._log_dir,
            f"translator_{datetime.now().strftime('%Y-%m-%d')}.log",
        )

    def _cleanup_old_logs(self) -> None:
        """Keep only the most recent MAX_LOG_FILES log files."""
        try:
            files = [
                f for f in os.listdir(self._log_dir)
                if f.startswith("translator_") and f.endswith(".log")
            ]
            files.sort(reverse=True)
            for f in files[self._max_files:]:
                try:
                    os.remove(os.path.join(self._log_dir, f))
                except OSError:
                    pass
        except OSError:
            pass

    def _rotate_if_needed(self) -> None:
        """If current log exceeds max_size, rename it with a sequence number."""
        path = self._current_log_path()
        if not os.path.exists(path):
            return
        try:
            if os.path.getsize(path) > self._max_size:
                # Find next available sequence number
                base = path.replace(".log", "")
                seq = 1
                while os.path.exists(f"{base}_{seq}.log"):
                    seq += 1
                os.rename(path, f"{base}_{seq}.log")
        except OSError:
            pass

    # ── logging ──

    def _log(self, tag: str, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} [{tag}] [{_LEVEL_LABEL[level].strip()}] {message}"

        with self._lock:
            self._buffer.append(line)
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]

            self._rotate_if_needed()
            try:
                with open(self._current_log_path(), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass

    def info(self, tag: str, message: str) -> None:
        self._log(tag, "INFO", message)

    def warn(self, tag: str, message: str) -> None:
        self._log(tag, "WARN", message)

    def error(self, tag: str, message: str) -> None:
        self._log(tag, "ERROR", message)

    # ── UI-facing ──

    def get_recent(self, n: int | None = None) -> list[str]:
        """Return recent log lines from the in-memory buffer (newest last)."""
        with self._lock:
            lines = self._buffer.copy()
        if n is not None:
            return lines[-n:]
        return lines

    def get_log_dir(self) -> str:
        return self._log_dir


# ── global singleton ──

_logger: Logger | None = None


def init_logger(log_dir: str | None = None) -> Logger:
    """Initialize the global logger singleton. Called once at app startup."""
    global _logger
    if _logger is None:
        _logger = Logger(log_dir)
    return _logger


def get_logger() -> Logger | None:
    """Get the global logger singleton. Returns None if not initialized."""
    return _logger
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd "y:/翻译器项目/ets2-translator" && python test_logger.py
```

Expected: All 4 test groups print PASS, final line `=== ALL LOGGER TESTS PASSED ===`

- [ ] **Step 5: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add logger.py test_logger.py && git commit -m "feat: add centralized logger module with rotation and buffer"
```

---

### Task 2: Add log calls to main.py (system events)

**Files:**
- Modify: `main.py:1-50` (imports + App.__init__)

- [ ] **Step 1: Add logger init at app startup**

In `main.py`, add import after existing imports (after line 32):

```python
from logger import init_logger, get_logger
```

In `App.__init__` (after `self.cfg = load_config()`, around line 39), add:

```python
# Initialize logger
self._log = init_logger()
self._log.info("SYS", f"翻译器启动 | {VERSION} | Python {sys.version.split()[0]} | 配置: {CONFIG_PATH}")
```

- [ ] **Step 2: Add shutdown log**

In `App._shutdown` (around line 180), add at the beginning:

```python
def _shutdown(self):
    if self._shutting_down:
        return
    self._shutting_down = True
    log = get_logger()
    if log:
        log.info("SYS", "翻译器关闭")
    # ... existing code ...
```

- [ ] **Step 3: Add single-instance log**

In `_ensure_single_instance` (around line 20), add before the MessageBox:

```python
def _ensure_single_instance():
    ctypes.windll.kernel32.CreateMutexW(None, True, _SINGLE_MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:
        # Log the duplicate instance attempt
        from logger import get_logger
        log = get_logger()
        if log:
            log.warn("SYS", "检测到重复实例，已退出")
        # ... existing MessageBox and return ...
```

- [ ] **Step 4: Add config save log**

In `App._tray_click_through` and `_switch_mode`, add a log call after `save_config`. Find:

```python
save_config(self.cfg)
```

Add after (in `_tray_click_through`):

```python
log = get_logger()
if log:
    log.info("SYS", f"鼠标穿透: {'开' if self.cfg.click_through else '关'}")
```

In `_switch_mode` (the callback version in App), add after `save_config`:

```python
log = get_logger()
if log:
    log.info("SYS", f"窗口模式切换: {self.cfg.window_mode}")
```

- [ ] **Step 5: Verify import**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "from logger import init_logger, get_logger; l=init_logger(); l.info('SYS','test'); print('main.py logger integration OK')"
```

Expected: prints "main.py logger integration OK"

- [ ] **Step 6: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add main.py && git commit -m "feat: add system event logging to main.py"
```

---

### Task 3: Add log calls to monitor.py (TMP events)

**Files:**
- Modify: `monitor.py:107-197` (ChatMonitor class)

- [ ] **Step 1: Add import**

At top of `monitor.py`, after existing imports:

```python
from logger import get_logger
```

- [ ] **Step 2: Add log calls in ChatMonitor**

In `ChatMonitor.run()`, after successfully finding a log file (around line 147), add:

```python
if self._log_path:
    self._last_size = os.path.getsize(self._log_path)
    self.status = f"已找到日志: {os.path.basename(self._log_path)}"
    log = get_logger()
    if log:
        log.info("TMP", f"聊天日志: {os.path.basename(self._log_path)} ({self._last_size} bytes)")
```

In `_check_log_switch()`, after detecting a switch (around line 131), add:

```python
if latest and latest != self._log_path:
    old = os.path.basename(self._log_path) if self._log_path else "None"
    self._log_path = latest
    self._last_size = os.path.getsize(latest)
    self._seen.clear()
    self.status = f"已切换日志: {os.path.basename(latest)} (旧: {old})"
    log = get_logger()
    if log:
        log.info("TMP", f"日志文件切换: {old} → {os.path.basename(latest)}")
    return True
```

In `ChatMonitor.stop()`, add:

```python
def stop(self):
    self.status = "已停止"
    self._stop_event.set()
    log = get_logger()
    if log:
        log.info("TMP", "聊天监控已停止")
```

- [ ] **Step 3: Add parse failure log**

In `_tail_once()`, modify the parse loop to log unexpected parse failures. After the existing `if msg is None: continue` (line 178), no change needed since None is normal for system messages. But we should add a counter for completely unparseable lines. Add after the for loop's `splitlines()`:

```python
for line in new_data.splitlines():
    if not line.strip():
        continue
    self_name = self._self_name
    msg = parse_line(line, self_name)
    if msg is None:
        # Only log if line looks like it should be chat (has brackets)
        if line.startswith("[") and ":" in line:
            pass  # Normal system message, skip silently
        continue
```

Actually — the above would add noise. Per the spec, only log when the log format genuinely changes (which would cause ALL lines to fail). Let's keep it simple and not log individual parse failures. The existing behavior of silently skipping non-chat lines is correct.

- [ ] **Step 4: Verify import**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "from logger import init_logger; init_logger(); from monitor import ChatMonitor; print('monitor.py logger integration OK')"
```

Expected: prints "monitor.py logger integration OK"

- [ ] **Step 5: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add monitor.py && git commit -m "feat: add TMP monitoring events to logger"
```

---

### Task 4: Add log calls to translator.py (LLM/Baidu events)

**Files:**
- Modify: `translator.py:1-60` (imports + Translator class init)
- Modify: `translator.py:119-240` (_flush methods)
- Modify: `translator.py:303-350` (test_connection, translate_to_english)
- Modify: `translator.py:397-443` (baidu functions)

- [ ] **Step 1: Add import and periodic stats counter**

At top of `translator.py`, after existing imports:

```python
from logger import get_logger
```

In `Translator.__init__`, add a periodic stats counter:

```python
def __init__(self, cfg: AppConfig, in_queue: Queue, out_queue: Queue):
    super().__init__(daemon=True)
    self.cfg = cfg
    self.in_queue = in_queue
    self.out_queue = out_queue
    self._stop_event = threading.Event()
    self._cache = LRUCache(CACHE_SIZE)
    self._client = httpx.Client(timeout=30.0)
    self.stats = TranslationStats()
    self._msg_since_log = 0  # counter for periodic stats logging
```

- [ ] **Step 2: Add periodic stats log in _flush methods**

In `Translator._flush()`, after `self.stats.translated += len(batch)` (line 122), add:

```python
def _flush(self, batch):
    if not batch:
        return
    self.stats.translated += len(batch)
    self._msg_since_log += len(batch)

    # Log stats every 50 messages
    if self._msg_since_log >= 50:
        self._msg_since_log = 0
        log = get_logger()
        if log:
            log.info("LLM", f"翻译统计: 翻译={self.stats.translated} 缓存={self.stats.cached} "
                    f"跳过={self.stats.self_skipped} 节省={self.stats.savings_pct()}")
    # ... rest unchanged ...
```

- [ ] **Step 3: Add error logging in _flush_llm**

In `_flush_llm`, in the except block (around line 153), add:

```python
except Exception as e:
    err_msg = self._format_error(e)
    log = get_logger()
    if log:
        log.error("LLM", f"翻译失败: {err_msg}")
    for msg in batch:
        # ... existing error display code ...
```

- [ ] **Step 4: Add error logging in _flush_baidu**

In `_flush_baidu`, in the except block (around line 174), add:

```python
except Exception as e:
    log = get_logger()
    if log:
        log.error("BDU", f"百度翻译失败: {e}")
    self.out_queue.put(DisplayMessage(
        # ... existing code ...
    ))
```

- [ ] **Step 5: Add Baidu override stats in _flush_hybrid**

In `_flush_hybrid`, add a counter for Baidu overrides and log them. After step 3 (compare and emit loop, around line 223-241), add before the loop:

```python
# Step 3: compare and emit
baidu_override_count = 0
for msg in batch:
    llm_trans = llm_results.get(msg.text, msg.text)
    baidu_trans = baidu_results.get(msg.text)
    if baidu_trans is not None and _translations_differ(llm_trans, baidu_trans):
        baidu_override_count += 1
        # ... existing override code ...
    else:
        # ... existing fallback code ...

if baidu_override_count > 0:
    log = get_logger()
    if log:
        log.info("BDU", f"百度纠错: {baidu_override_count}/{len(batch)} 条被覆盖")
```

- [ ] **Step 6: Add connectivity test logging**

In `test_connection()` (around line 303), add on success path:

```python
try:
    # ... existing test code ...
    content = data["choices"][0]["message"]["content"].strip()
    log = get_logger()
    if log:
        log.info("LLM", f"连通测试 OK | {model} @ {endpoint}")
    return True, f"连通成功 — {content[:60]}"
```

On failure paths, the function already returns descriptive errors. We just log them:

```python
except httpx.ConnectError:
    log = get_logger()
    if log:
        log.error("LLM", "连通测试失败: 无法连接到 API 服务器")
    return False, "无法连接到 API 服务器，请检查地址和网络"
```

Add similar `get_logger()` error calls for other except branches in `test_connection()`.

- [ ] **Step 7: Add Baidu connectivity test logging**

In `test_baidu_connection()` (around line 435), add:

```python
def test_baidu_connection(appid: str, secret: str) -> tuple:
    if not appid or not secret:
        return False, "请填写百度翻译 APP ID 和密钥"
    try:
        result = translate_via_baidu(appid, secret, "Hello")
        log = get_logger()
        if log:
            log.info("BDU", "连通测试 OK | 百度翻译 API 标准版")
        return True, f"连通成功 — {result[:60]}"
    except Exception as e:
        log = get_logger()
        if log:
            log.error("BDU", f"连通测试失败: {e}")
        return False, f"连通失败: {e}"
```

- [ ] **Step 8: Add translate_to_english error logging**

In `translate_to_english()` (around line 356), the function raises exceptions on error which are caught by the caller in overlay.py. Add a log before the raise doesn't work well. Instead, the caller already handles this. No change needed here — the caller in overlay.py will log it.

- [ ] **Step 9: Verify import**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "from logger import init_logger; init_logger(); from translator import Translator; print('translator.py logger integration OK')"
```

Expected: prints "translator.py logger integration OK"

- [ ] **Step 10: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add translator.py && git commit -m "feat: add LLM and Baidu translation events to logger"
```

---

### Task 5: Add log calls to overlay.py (hotkey events)

**Files:**
- Modify: `overlay.py:1-30` (imports)
- Modify: `overlay.py:651-682` (hotkey poller, _on_copy_hotkey, _on_enter_hotkey)
- Modify: `overlay.py:702-731` (_do_translate error)
- Modify: `overlay.py:835-848` (_click_on_widget)

- [ ] **Step 1: Add import**

At top of `overlay.py`, after existing imports:

```python
from logger import get_logger
```

- [ ] **Step 2: Add hotkey registration log**

In `_start_hotkey_poller` (around line 613), after successful parse:

```python
def _start_hotkey_poller(self):
    mods, vk = self._parse_hotkey(self.cfg.send_hotkey)
    if vk == 0:
        return

    log = get_logger()
    if log:
        log.info("HOT", f"全局热键: {self._format_hotkey(self.cfg.send_hotkey)}")
    # ... existing poller start code ...
```

- [ ] **Step 3: Add hotkey change log**

In `update_send_hotkey` (around line 677), add:

```python
def update_send_hotkey(self, new_hotkey: str):
    self._stop_hotkey_poller()
    self.cfg.send_hotkey = new_hotkey
    self._update_hotkey_hint()
    self._start_hotkey_poller()
    log = get_logger()
    if log:
        log.info("HOT", f"热键变更: {self._format_hotkey(new_hotkey)}")
```

- [ ] **Step 4: Add translate error log**

In `_on_translate_error` (around line 726), add:

```python
def _on_translate_error(self, error: str):
    self._sending = False
    self.send_entry.config(state=tk.NORMAL)
    self.send_hint.config(text=" 翻译失败 ", fg="#f44747")
    self.root.after(5000, lambda: self._update_hotkey_hint())
    self.add_message("System", "发送翻译失败", error, is_self=True)
    log = get_logger()
    if log:
        log.error("LLM", f"发送翻译失败: {error}")
```

- [ ] **Step 5: Verify import**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "from logger import init_logger; init_logger(); import overlay; print('overlay.py logger integration OK')"
```

Expected: prints "overlay.py logger integration OK"

- [ ] **Step 6: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add overlay.py && git commit -m "feat: add hotkey events to logger"
```

---

### Task 6: Add log calls to update.py (update events)

**Files:**
- Modify: `update.py:1-20` (imports)
- Modify: `update.py:20-39` (check_for_update)
- Modify: `update.py:53-65` (download_update)
- Modify: `update.py:88-107` (apply_update)

- [ ] **Step 1: Add import**

At top of `update.py`, after existing imports:

```python
from logger import get_logger
```

- [ ] **Step 2: Add update check logging**

In `check_for_update()` (around line 20), add after successful parsing:

```python
if _version_newer(latest, VERSION):
    # ... existing code to find URL ...
    log = get_logger()
    if log:
        log.info("UPD", f"发现新版本: {latest} → {url}")
    return True, latest, url

# No update
log = get_logger()
if log:
    log.info("UPD", f"已是最新版本: {VERSION}")
return False, latest, ""
```

And in the except block:

```python
except (URLError, OSError, json.JSONDecodeError, KeyError):
    log = get_logger()
    if log:
        log.warn("UPD", "检查更新失败: 无法连接到 GitHub")
    return False, "", ""
```

- [ ] **Step 3: Add download logging**

In `download_update()` (around line 53):

```python
def download_update(url: str, progress_cb: callable | None = None) -> str | None:
    try:
        tmp = tempfile.mktemp(suffix=".exe", prefix="ets2_update_")
        log = get_logger()
        if log:
            log.info("UPD", f"开始下载更新: {url}")
        _download_with_progress(url, tmp, progress_cb)
        if log:
            log.info("UPD", "更新下载完成")
        return tmp
    except (URLError, OSError) as e:
        if progress_cb:
            progress_cb(-1)
        log = get_logger()
        if log:
            log.error("UPD", f"下载失败: {e}")
        return None
```

- [ ] **Step 4: Add apply update logging**

In `apply_update()` (around line 88):

```python
def apply_update(new_exe_path: str, own_exe_path: str) -> None:
    log = get_logger()
    if log:
        log.info("UPD", f"安装更新: {new_exe_path} → {own_exe_path}")
    # ... existing batch script code ...
```

- [ ] **Step 5: Verify import**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "from logger import init_logger; init_logger(); import update; print('update.py logger integration OK')"
```

Expected: prints "update.py logger integration OK"

- [ ] **Step 6: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add update.py && git commit -m "feat: add update events to logger"
```

---

### Task 7: Add log tab to SettingsDialog in main.py

**Files:**
- Modify: `main.py:370-708` (SettingsDialog class)

- [ ] **Step 1: Add import for logger in main.py**

Already added in Task 2. No additional import needed.

- [ ] **Step 2: Restructure SettingsDialog._build() to add tab bar**

The current `_build()` method packs sections into a single scrollable frame. We need to:

1. Add a tab bar at the top with 4 tabs: "API 配置", "快捷键", "外观", "📋 日志"
2. Move existing sections into tab-specific frames
3. Add log viewer in the 4th tab

Replace the current `_build()` method. The full replacement is:

```python
def _build(self):
    page_bg = self._PAGE_BG

    # ---- ttk dark theme styling (same as before) ----
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar",
                    background="#161b22", troughcolor="#0d1117",
                    arrowcolor="#8b949e", bordercolor="#161b22",
                    gripcount=0, darkcolor="#30363d", lightcolor="#30363d")
    style.map("Vertical.TScrollbar",
              background=[("active", "#30363d"), ("pressed", "#484f58")])
    style.configure("TSpinbox",
                    fieldbackground="#0d1117", background="#21262d",
                    foreground="#e6edf3", bordercolor="#30363d",
                    darkcolor="#30363d", lightcolor="#30363d",
                    arrowcolor="#8b949e", selectbackground="#1f6feb",
                    selectforeground="#ffffff")
    style.map("TSpinbox",
              fieldbackground=[("readonly", "#0d1117")],
              background=[("active", "#30363d")])
    style.configure("TCombobox",
                    fieldbackground="#0d1117", background="#21262d",
                    foreground="#e6edf3", bordercolor="#30363d",
                    darkcolor="#30363d", lightcolor="#30363d",
                    arrowcolor="#8b949e", selectbackground="#1f6feb",
                    selectforeground="#ffffff")
    style.map("TCombobox",
              fieldbackground=[("readonly", "#0d1117")],
              background=[("active", "#30363d"), ("hover", "#30363d")])
    self.top.option_add("*TCombobox*Listbox.background", "#161b22")
    self.top.option_add("*TCombobox*Listbox.foreground", "#e6edf3")
    self.top.option_add("*TCombobox*Listbox.selectBackground", "#1f6feb")
    self.top.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # ---- outer layout ----
    outer = tk.Frame(self.top, bg=page_bg)
    outer.pack(fill=tk.BOTH, expand=True)
    outer.rowconfigure(1, weight=1)
    outer.columnconfigure(0, weight=1)

    # ---- tab bar ----
    self._tab_bar = tk.Frame(outer, bg=page_bg, height=36)
    self._tab_bar.grid(row=0, column=0, sticky="ew", padx=4, pady=(8, 0))
    self._tab_bar.grid_propagate(False)

    self._tabs = {}
    self._tab_frames = {}
    tab_names = [
        ("api", "API 配置"),
        ("hotkeys", "快捷键"),
        ("appearance", "外观"),
        ("logs", "📋 日志"),
    ]
    for i, (key, label) in enumerate(tab_names):
        btn = tk.Label(self._tab_bar, text=label,
                       bg=self._CARD_BG, fg=self._TEXT_SEC,
                       font=("Microsoft YaHei", 10),
                       padx=16, pady=6, cursor="hand2")
        btn.pack(side=tk.LEFT, padx=(0, 2))
        btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg="#21262d", fg=self._TEXT))
        btn.bind("<Leave>", lambda e, b=btn, k=key: self._tab_hover_leave(b, k))
        self._tabs[key] = btn

    # ---- content area (stack of tab frames, only one visible) ----
    self._content_area = tk.Frame(outer, bg=page_bg)
    self._content_area.grid(row=1, column=0, sticky="nsew")
    self._content_area.rowconfigure(0, weight=1)
    self._content_area.columnconfigure(0, weight=1)

    # ---- build each tab's frame ----
    self._build_api_tab()
    self._build_hotkeys_tab()
    self._build_appearance_tab()
    self._build_logs_tab()

    # ---- activate first tab ----
    self._active_tab = None
    self._switch_tab("api")
```

- [ ] **Step 3: Extract API tab into a method**

The API card content (Card 1 + Baidu sub-card) from the original `_build()` goes into `_build_api_tab()`:

```python
def _build_api_tab(self):
    """Build the API configuration tab."""
    frame = self._tab_frames["api"] = tk.Frame(self._content_area, bg=self._PAGE_BG)
    frame.columnconfigure(0, weight=1)

    # Scrollable canvas
    canvas = tk.Canvas(frame, bg=self._PAGE_BG, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)

    inner = tk.Frame(canvas, bg=self._PAGE_BG, padx=20, pady=16)
    inner.columnconfigure(0, weight=1)
    inner_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_inner_configure)

    def _on_canvas_configure(event):
        canvas.itemconfig(inner_id, width=event.width)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    def _on_destroy(event):
        canvas.unbind_all("<MouseWheel>")
    self.top.bind("<Destroy>", _on_destroy)

    # Card 1: API
    self._section_label(inner, "TRANSLATION API  /  翻译接口").pack(
        fill=tk.X, pady=(0, 8))
    card1 = self._card(inner, padx=16, pady=12)
    card1.pack(fill=tk.X, pady=(0, 4))
    card1.columnconfigure(1, weight=1)

    r = 0
    self.ep_entry = self._entry(card1)
    r = self._row(card1, r, "API Endpoint / 地址", self.ep_entry)

    self.key_entry = self._entry(card1, show="*")
    r = self._row(card1, r, "API Key / 密钥", self.key_entry)

    self.model_entry = self._entry(card1)
    r = self._row(card1, r, "Model / 模型", self.model_entry)

    self.backend_var = tk.StringVar(value=self.cfg.translation_backend)
    self.backend_combo = ttk.Combobox(
        card1, textvariable=self.backend_var,
        values=["llm", "baidu", "llm+baidu"],
        state="readonly", width=18,
        font=("Microsoft YaHei", 10))
    self.backend_combo.bind("<<ComboboxSelected>>", self._on_backend_changed)
    r = self._row(card1, r, "Backend / 翻译后端", self.backend_combo)

    self.lang_var = tk.StringVar(value=self.cfg.target_language)
    self.lang_combo = ttk.Combobox(
        card1, textvariable=self.lang_var,
        values=["zh-CN", "en", "ja", "ko", "fr", "de", "es", "ru", "pt", "it"],
        state="readonly", width=18,
        font=("Microsoft YaHei", 10))
    r = self._row(card1, r, "Target Language / 目标语言", self.lang_combo)

    # Baidu sub-card
    self.baidu_group = tk.Frame(card1, bg=self._INPUT_BG,
                                 highlightbackground=self._CARD_BORDER,
                                 highlightthickness=1)
    self.baidu_group.columnconfigure(1, weight=1)
    tk.Label(self.baidu_group, text="Baidu Translate",
             bg=self._INPUT_BG, fg=self._TEXT_SEC,
             font=("Microsoft YaHei", 8, "bold"), anchor=tk.W).grid(
        row=0, column=0, columnspan=2, sticky=tk.W, padx=12, pady=(8, 2))
    self.baidu_appid_entry = self._entry(self.baidu_group, width=42)
    self.baidu_appid_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW,
                                 padx=12, pady=(4, 2))
    tk.Label(self.baidu_group, text="APP ID",
             bg=self._INPUT_BG, fg=self._TEXT_SEC,
             font=("Microsoft YaHei", 8), anchor=tk.W).grid(
        row=2, column=0, sticky=tk.W, padx=12, pady=(0, 2))
    self.baidu_secret_entry = self._entry(self.baidu_group, show="*", width=42)
    self.baidu_secret_entry.grid(row=3, column=0, columnspan=2, sticky=tk.EW,
                                  padx=12, pady=(4, 2))
    tk.Label(self.baidu_group, text="Secret / 密钥",
             bg=self._INPUT_BG, fg=self._TEXT_SEC,
             font=("Microsoft YaHei", 8), anchor=tk.W).grid(
        row=4, column=0, sticky=tk.W, padx=12, pady=(0, 2))
    tk.Label(self.baidu_group,
             text="免费申请  fanyi-api.baidu.com  ·  标准版每月 500 万字符",
             bg=self._INPUT_BG, fg=self._TEXT_SEC,
             font=("Microsoft YaHei", 7)).grid(
        row=5, column=0, columnspan=2, sticky=tk.W, padx=12, pady=(2, 10))
    self.baidu_group.grid(row=r, column=0, columnspan=2, sticky=tk.EW,
                           padx=12, pady=(6, 12))
    self._on_backend_changed()

    # Test button row
    btn_row = tk.Frame(inner, bg=self._PAGE_BG)
    btn_row.pack(fill=tk.X, pady=(24, 8))

    self._test_btn = self._pill_btn(btn_row, "Test / 测试连接",
                                     self._test_connection, accent=False)
    self._test_btn.pack(side=tk.LEFT, padx=(0, 8))

    self._test_status = tk.Label(btn_row, text="", bg=self._PAGE_BG, fg=self._TEXT_SEC,
                                  font=("Microsoft YaHei", 9), anchor=tk.W)
    self._test_status.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
```

- [ ] **Step 4: Extract hotkeys tab into a method**

```python
def _build_hotkeys_tab(self):
    """Build the hotkeys configuration tab."""
    frame = self._tab_frames["hotkeys"] = tk.Frame(self._content_area, bg=self._PAGE_BG)
    frame.columnconfigure(0, weight=1)

    # Scrollable canvas
    canvas = tk.Canvas(frame, bg=self._PAGE_BG, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)

    inner = tk.Frame(canvas, bg=self._PAGE_BG, padx=20, pady=16)
    inner.columnconfigure(0, weight=1)
    inner_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_inner_configure)

    def _on_canvas_configure(event):
        canvas.itemconfig(inner_id, width=event.width)
    canvas.bind("<Configure>", _on_canvas_configure)

    # Card 2: Hotkeys
    self._section_label(inner, "HOTKEYS  /  快捷键").pack(
        fill=tk.X, pady=(0, 8))
    card2 = self._card(inner, padx=16, pady=12)
    card2.pack(fill=tk.X, pady=(0, 4))
    card2.columnconfigure(1, weight=1)

    r = 0
    r = self._row(card2, r, "Copy Hotkey / 复制",
                  self._hotkey_capture(card2, self.cfg.copy_hotkey, "_copy_cap"))
    r = self._row(card2, r, "Send Hotkey / 发送",
                  self._hotkey_capture(card2, self.cfg.enter_hotkey, "_enter_cap"))
    r = self._row(card2, r, "Focus Key / 呼出输入框",
                  self._hotkey_capture(card2, self.cfg.send_hotkey, "_focus_cap"))

    tk.Label(card2,
             text="按下组合键进行捕获",
             bg=self._CARD_BG, fg=self._RED,
             font=("Microsoft YaHei", 8), anchor=tk.W).grid(
        row=r, column=1, sticky=tk.W, padx=(0, 16), pady=(4, 12))

    # Bottom buttons
    btn_row = tk.Frame(inner, bg=self._PAGE_BG)
    btn_row.pack(fill=tk.X, pady=(24, 8))

    self._pill_btn(btn_row, "Cancel / 取消", self._on_close, accent=False).pack(
        side=tk.RIGHT, padx=4)
    self._pill_btn(btn_row, "Save / 保存", self._save, accent=True).pack(
        side=tk.RIGHT, padx=4)
```

- [ ] **Step 5: Extract appearance tab into a method**

```python
def _build_appearance_tab(self):
    """Build the appearance configuration tab."""
    frame = self._tab_frames["appearance"] = tk.Frame(self._content_area, bg=self._PAGE_BG)
    frame.columnconfigure(0, weight=1)

    # Scrollable canvas
    canvas = tk.Canvas(frame, bg=self._PAGE_BG, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)

    inner = tk.Frame(canvas, bg=self._PAGE_BG, padx=20, pady=16)
    inner.columnconfigure(0, weight=1)
    inner_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_inner_configure)

    def _on_canvas_configure(event):
        canvas.itemconfig(inner_id, width=event.width)
    canvas.bind("<Configure>", _on_canvas_configure)

    # Card 3: Appearance
    self._section_label(inner, "APPEARANCE  /  外观").pack(
        fill=tk.X, pady=(0, 8))
    card3 = self._card(inner, padx=16, pady=12)
    card3.pack(fill=tk.X, pady=(0, 4))
    card3.columnconfigure(1, weight=1)

    r = 0
    # Opacity
    self._label(card3, "Window Opacity / 窗口透明度").grid(
        row=r, column=0, sticky=tk.W, pady=5, padx=(16, 8))
    opacity_row = tk.Frame(card3, bg=self._CARD_BG)
    opacity_row.columnconfigure(0, weight=1)
    self.opacity_scale = tk.Scale(opacity_row, from_=0.1, to=1.0, resolution=0.01,
                                   orient=tk.HORIZONTAL, bg=self._CARD_BG, fg=self._TEXT,
                                   highlightthickness=0, bd=0, length=200,
                                   troughcolor="#21262d", activebackground=self._ACCENT,
                                   command=self._on_opacity_change)
    self.opacity_scale.grid(row=0, column=0, sticky=tk.EW)
    self.opacity_val = tk.Label(opacity_row, text="0.80", bg=self._CARD_BG,
                                 fg=self._ACCENT, font=("Microsoft YaHei", 10, "bold"),
                                 width=4, anchor=tk.E)
    self.opacity_val.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))
    opacity_row.grid(row=r, column=1, sticky=tk.EW, padx=(0, 16))
    r += 1

    self.font_spin = ttk.Spinbox(card3, from_=8, to=24, width=6, font=("Microsoft YaHei", 10))
    r = self._row(card3, r, "Font Size / 字体大小", self.font_spin)

    self.max_spin = ttk.Spinbox(card3, from_=10, to=200, width=6, font=("Microsoft YaHei", 10))
    r = self._row(card3, r, "Max Messages / 最大消息数", self.max_spin)

    self.name_entry = self._entry(card3)
    r = self._row(card3, r, "Game Name / 游戏 ID", self.name_entry)

    self.mode_var = tk.StringVar(value=self.cfg.window_mode)
    mode_frame = tk.Frame(card3, bg=self._CARD_BG)
    for val, lbl in [("standalone", "Standalone / 标准"), ("overlay", "Overlay / 悬浮")]:
        rb = tk.Radiobutton(mode_frame, text=lbl, variable=self.mode_var, value=val,
                            bg=self._CARD_BG, fg=self._TEXT,
                            font=("Microsoft YaHei", 10),
                            selectcolor=self._CARD_BG,
                            activebackground=self._CARD_BG,
                            activeforeground=self._ACCENT,
                            command=self._on_mode_changed)
        rb.pack(side=tk.LEFT, padx=(0, 12))
    r = self._row(card3, r, "Window Mode / 窗口模式", mode_frame)

    self.click_var = tk.BooleanVar(value=self.cfg.click_through)
    cb = tk.Checkbutton(card3, text="Click-through / 鼠标穿透 (仅悬浮模式)",
                        variable=self.click_var,
                        bg=self._CARD_BG, fg=self._TEXT,
                        font=("Microsoft YaHei", 10),
                        selectcolor=self._CARD_BG,
                        activebackground=self._CARD_BG,
                        activeforeground=self._ACCENT)
    cb.grid(row=r, column=0, columnspan=2, sticky=tk.W, padx=16, pady=(4, 12))

    # Bottom buttons
    btn_row = tk.Frame(inner, bg=self._PAGE_BG)
    btn_row.pack(fill=tk.X, pady=(24, 8))

    self._pill_btn(btn_row, "Cancel / 取消", self._on_close, accent=False).pack(
        side=tk.RIGHT, padx=4)
    self._pill_btn(btn_row, "Save / 保存", self._save, accent=True).pack(
        side=tk.RIGHT, padx=4)
```

- [ ] **Step 6: Build the logs tab**

```python
def _build_logs_tab(self):
    """Build the log viewer tab."""
    frame = self._tab_frames["logs"] = tk.Frame(self._content_area, bg=self._PAGE_BG)
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    # Log text widget (read-only, dark, monospace-ish)
    self.log_text = tk.Text(
        frame,
        font=("Consolas", 9),
        bg="#0d1117", fg="#8b949e",
        wrap=tk.WORD, state=tk.DISABLED,
        borderwidth=0, highlightthickness=0,
        padx=8, pady=8,
        insertbackground="#8b949e",
    )
    vbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
    self.log_text.configure(yscrollcommand=vbar.set)
    self.log_text.grid(row=0, column=0, sticky="nsew")
    vbar.grid(row=0, column=1, sticky="ns")

    # Color tags for log levels
    self.log_text.tag_configure("info", foreground="#8b949e")
    self.log_text.tag_configure("warn", foreground="#d29922")
    self.log_text.tag_configure("error", foreground="#f85149")

    # Bottom button row
    btn_row = tk.Frame(frame, bg=self._PAGE_BG)
    btn_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 4), padx=8)

    self._pill_btn(btn_row, "📂 打开日志文件夹", self._open_log_dir, accent=False).pack(
        side=tk.LEFT)

    self._pill_btn(btn_row, "🔄 刷新", self._refresh_logs, accent=False).pack(
        side=tk.LEFT, padx=(8, 0))

    self._pill_btn(btn_row, "Cancel / 取消", self._on_close, accent=False).pack(
        side=tk.RIGHT, padx=4)
    self._pill_btn(btn_row, "Save / 保存", self._save, accent=True).pack(
        side=tk.RIGHT, padx=4)
```

- [ ] **Step 7: Add tab switching method**

```python
def _switch_tab(self, key: str) -> None:
    """Switch to the given tab, showing its frame and highlighting its button."""
    if self._active_tab == key:
        return

    # Deactivate all tabs
    for k, btn in self._tabs.items():
        btn.configure(bg=self._CARD_BG, fg=self._TEXT_SEC)

    # Hide all frames
    for f in self._tab_frames.values():
        f.grid_remove()

    # Activate selected
    self._tabs[key].configure(bg="#1f6feb", fg="#ffffff")
    self._tab_frames[key].grid(row=0, column=0, sticky="nsew")
    self._active_tab = key

    # Refresh logs when switching to logs tab
    if key == "logs":
        self._refresh_logs()

def _tab_hover_leave(self, btn: tk.Label, key: str) -> None:
    """Reset tab button color on mouse leave."""
    if self._active_tab == key:
        btn.configure(bg="#1f6feb", fg="#ffffff")
    else:
        btn.configure(bg=self._CARD_BG, fg=self._TEXT_SEC)
```

- [ ] **Step 8: Add log refresh and open folder methods**

```python
def _refresh_logs(self) -> None:
    """Reload log content from the logger buffer into the text widget."""
    if not hasattr(self, 'log_text'):
        return
    log = get_logger()
    lines = log.get_recent() if log else []

    self.log_text.configure(state=tk.NORMAL)
    self.log_text.delete("1.0", tk.END)

    for line in lines:
        if "[ERROR]" in line:
            self.log_text.insert(tk.END, line + "\n", "error")
        elif "[WARN]" in line:
            self.log_text.insert(tk.END, line + "\n", "warn")
        else:
            self.log_text.insert(tk.END, line + "\n", "info")

    self.log_text.configure(state=tk.DISABLED)
    self.log_text.see(tk.END)


def _open_log_dir(self) -> None:
    """Open the log directory in Windows Explorer."""
    import os
    log = get_logger()
    if log:
        log_dir = log.get_log_dir()
        if os.path.isdir(log_dir):
            os.startfile(log_dir)
```

- [ ] **Step 9: Add mousewheel binding for logs tab**

Add mousewheel scrolling to the log text widget. In `_switch_tab`, when switching to "logs":

```python
def _on_log_mousewheel(event):
    self.log_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
```

Bind it in `_build_logs_tab`:

```python
self.log_text.bind("<MouseWheel>", _on_log_mousewheel)
```

Actually, since `_on_log_mousewheel` needs `self`, make it a method. Add to `_build_logs_tab`:

```python
self.log_text.bind("<MouseWheel>", self._on_log_mousewheel)
```

And add the method:

```python
def _on_log_mousewheel(self, event) -> None:
    self.log_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
```

- [ ] **Step 10: Remove bottom buttons from API and hotkeys tabs**

The Cancel/Save buttons should only appear on the Appearance and Logs tabs (the last two tabs). In `_build_api_tab` and `_build_hotkeys_tab`, the bottom buttons were not included — only the test button is in API and no bottom buttons in hotkeys. The Cancel/Save buttons are in both appearance and logs tabs.

- [ ] **Step 11: Verify the module loads without errors**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from logger import init_logger
init_logger()
import main
print('main.py SettingsDialog with tabs OK')
"
```

Expected: prints "main.py SettingsDialog with tabs OK" (no Tk errors in headless check; the Tk root isn't created so window methods won't run)

- [ ] **Step 12: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add main.py && git commit -m "feat: add log viewer tab to settings dialog"
```

---

### Task 8: Final integration verification

**Files:**
- Verify: all modules import cleanly together

- [ ] **Step 1: Run full import check**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from logger import init_logger, get_logger, Logger
from config import AppConfig, load_config, VERSION
from message_types import DisplayMessage, TranslationStats
from win32_constants import vk_code
from monitor import ChatMonitor, find_latest_log, parse_line
from translator import Translator, test_connection, test_baidu_connection
from overlay import OverlayWindow
from input_sender import send_chat_message, set_debug_enabled
from update import check_for_update
import main
print('=== ALL MODULES IMPORT OK ===')
"
```

Expected: prints "=== ALL MODULES IMPORT OK ===" (may show Tk startup warnings, that's fine)

- [ ] **Step 2: Run logger tests again to confirm no regressions**

```bash
cd "y:/翻译器项目/ets2-translator" && python test_logger.py
```

Expected: `=== ALL LOGGER TESTS PASSED ===`

- [ ] **Step 3: Verify log file is created and populated**

Since we can't fully run the Tkinter app headlessly, verify the logger writes to file:

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from logger import init_logger, get_logger
import os
log = init_logger()
log.info('SYS', 'integration test')
log.warn('TMP', 'log dir status test')
log.error('LLM', 'connection failure test')
log_dir = log.get_log_dir()
log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
print(f'Log dir: {log_dir}')
print(f'Log files: {log_files}')
assert len(log_files) >= 1, 'No log file created!'
print('Log file creation OK')

# Check content
import glob
latest = sorted(glob.glob(os.path.join(log_dir, 'translator_*.log')))[-1]
with open(latest, 'r', encoding='utf-8') as f:
    content = f.read()
assert 'integration test' in content
assert 'connection failure test' in content
print('Log content OK')
print('=== INTEGRATION TEST PASSED ===')
"
```

Expected: prints "=== INTEGRATION TEST PASSED ==="

- [ ] **Step 4: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add -A && git commit -m "test: add integration verification for logging feature"
```

---

## Execution Order & Dependencies

```
Task 1 (logger.py) ──→ Task 2 (main.py system) ──→ Task 7 (SettingsDialog tabs)
                    ├──→ Task 3 (monitor.py)
                    ├──→ Task 4 (translator.py)
                    ├──→ Task 5 (overlay.py)
                    └──→ Task 6 (update.py)
                                              ──→ Task 8 (integration verify)
```

Task 1 must complete first. Tasks 2-6 are independent of each other and can run in parallel. Task 7 depends on Task 2 (main.py already imports logger). Task 8 is final.

**Total estimated commits: 8**
