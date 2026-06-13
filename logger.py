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

_LEVEL_LABEL = {"INFO": "INFO", "WARN": "WARN", "ERROR": "ERROR"}


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
        self._file = None
        os.makedirs(self._log_dir, exist_ok=True)
        self._cleanup_old_logs()

    # --- file management ---

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
                base = path.replace(".log", "")
                seq = 1
                while os.path.exists(f"{base}_{seq}.log"):
                    seq += 1
                os.rename(path, f"{base}_{seq}.log")
        except OSError:
            pass

    # --- logging ---

    def _log(self, tag: str, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} [{tag}] [{_LEVEL_LABEL[level]}] {message}"

        with self._lock:
            self._buffer.append(line)
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]

            self._rotate_if_needed()
            try:
                if self._file is None:
                    self._file = open(self._current_log_path(), "a", encoding="utf-8")
                self._file.write(line + "\n")
                self._file.flush()
            except OSError:
                pass

    def info(self, tag: str, message: str) -> None:
        self._log(tag, "INFO", message)

    def close(self) -> None:
        """Close the persistent file handle if open."""
        with self._lock:
            if self._file is not None:
                try:
                    self._file.close()
                except OSError:
                    pass
                self._file = None

    def warn(self, tag: str, message: str) -> None:
        self._log(tag, "WARN", message)

    def error(self, tag: str, message: str) -> None:
        self._log(tag, "ERROR", message)

    # --- UI-facing ---

    def get_recent(self, n: int | None = None) -> list[str]:
        """Return recent log lines from the in-memory buffer (newest last)."""
        if n is not None and n <= 0:
            return []
        with self._lock:
            lines = self._buffer.copy()
        if n is not None:
            return lines[-n:]
        return lines

    def get_log_dir(self) -> str:
        return self._log_dir


# --- global singleton ---

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
