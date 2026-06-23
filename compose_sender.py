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
    """Handles the full compose->translate->send->confirm pipeline.

    Uses file-based chat log confirmation - does NOT touch the
    monitor->translator message queue, so no messages are stolen.
    """

    __slots__ = ("cfg", "_busy_lock")

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._busy_lock = threading.Lock()

    # -- public API --

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

    # -- internal --

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
            text: The text to search for (will be normalized).
            timeout: Maximum seconds to wait.
            log_path: Override path (for testing). If None, auto-detect via find_latest_log().
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

        # Compile the chat line regex (same pattern as monitor.py CHAT_LINE_RE)
        _CHAT_RE = re.compile(
            r"^\[(?P<channel>.+?)\]\s+"
            r"\[(?P<time>\d{2}:\d{2}:\d{2})\]\s+"
            r"(?P<player>.+?)\s+\([A-Z]?\s*\d+\):\s+"
            r"(?P<text>.+)$"
        )

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                # Seek to end - only read lines written after this point
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
