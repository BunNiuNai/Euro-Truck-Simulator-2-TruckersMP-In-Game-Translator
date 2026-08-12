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

_LEVEL_LABEL = {"INFO": "INFO", "WARN": "WARN", "ERROR": "ERROR", "DEBUG": "DEBUG"}


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
        self._current_date = ""  # track date for midnight rollover
        try:
            os.makedirs(self._log_dir, exist_ok=True)
        except OSError:
            pass  # log directory unavailable — logging will be memory-only
        self._cleanup_old_logs()

    # --- file management ---

    def _current_log_path(self) -> str:
        return os.path.join(
            self._log_dir,
            f"translator_{datetime.now().strftime('%Y-%m-%d')}.log",
        )

    def _close_file(self) -> None:
        """Close the persistent file handle if open (thread-safe)."""
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None

    def _ensure_file_open(self) -> None:
        """Re-open the current log file if needed (called after delete)."""
        today = datetime.now().strftime('%Y-%m-%d')
        if self._file is None or today != self._current_date:
            if self._file is not None:
                self._close_file()
            self._current_date = today
            try:
                self._file = open(self._current_log_path(), "a", encoding="utf-8")
            except OSError:
                pass

    def _cleanup_old_logs(self) -> None:
        """Remove log files older than 7 days (weekly cleanup)."""
        try:
            cutoff = datetime.now().timestamp() - 7 * 86400
            for f in os.listdir(self._log_dir):
                if f.startswith("translator_") and f.endswith(".log"):
                    fpath = os.path.join(self._log_dir, f)
                    try:
                        if os.path.getmtime(fpath) < cutoff:
                            os.remove(fpath)
                    except OSError:
                        pass
        except OSError:
            pass

    def _delete_log_files(self, prefix: str) -> tuple[int, list[str]]:
        """Delete log files matching a prefix. Returns (deleted_count, [errors]).
        Caller MUST hold self._lock before calling if prefix == "translator_".
        Closes/opens the translator file handle for translator_ prefix.
        """
        errors: list[str] = []
        deleted = 0

        # Close the translator file handle before deleting translator files
        if prefix == "translator_":
            self._close_file()

        try:
            for f in os.listdir(self._log_dir):
                if f.startswith(prefix) and f.endswith(".log"):
                    fpath = os.path.join(self._log_dir, f)
                    try:
                        os.remove(fpath)
                        deleted += 1
                    except OSError as e:
                        errors.append(f"{f}: {e}")
        except OSError as e:
            errors.append(str(e))

        # Re-open translator file after deletion — skip: lazily reopened on next _log() call
        return deleted, errors

    def delete_translator_logs(self) -> int:
        """Delete all translator log files. Returns count of deleted files.
        Closes the current file handle first so Windows can delete it.
        Clears the in-memory buffer so UI reflects the deletion.
        """
        with self._lock:
            deleted, _errors = self._delete_log_files("translator_")
            self._buffer.clear()
        return deleted

    def delete_all_logs(self) -> int:
        """Delete all log files (both translator and message). Returns total count.
        The in-memory buffer is cleared.
        """
        with self._lock:
            t_deleted, _t_errs = self._delete_log_files("translator_")
            m_deleted, _m_errs = self._delete_log_files("messages_")
            self._buffer.clear()
        return t_deleted + m_deleted

    def _rotate_if_needed(self) -> None:
        """If current log exceeds max_size, rename it with a sequence number."""
        path = self._current_log_path()
        if not os.path.exists(path):
            return
        try:
            if os.path.getsize(path) > self._max_size:
                # Close file handle first — os.rename fails on Windows if file is open
                self._close_file()
                base = path.replace(".log", "")
                seq = 1
                while os.path.exists(f"{base}_{seq}.log"):
                    seq += 1
                os.replace(path, f"{base}_{seq}.log")  # os.replace is atomic, handles existing dest
        except OSError:
            pass

    # --- logging ---

    def _log(self, tag: str, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} [{tag}] [{_LEVEL_LABEL.get(level, level)}] {message}"

        with self._lock:
            self._buffer.append(line)
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]

            self._rotate_if_needed()
            try:
                self._ensure_file_open()
                if self._file is not None:
                    self._file.write(line + "\n")
                    self._file.flush()
            except OSError:
                pass

    def info(self, tag: str, message: str) -> None:
        self._log(tag, "INFO", message)

    def close(self) -> None:
        """Close the persistent file handle if open."""
        with self._lock:
            self._close_file()

    def warn(self, tag: str, message: str) -> None:
        self._log(tag, "WARN", message)

    def error(self, tag: str, message: str) -> None:
        self._log(tag, "ERROR", message)

    def translation_log(self, provider_label: str, model: str, original: str, translated: str) -> None:
        """Write a translated message to the unified log file.
        Format: YYYY-MM-DD HH:MM:SS - provider_label-model - original - translated
        """
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} - {provider_label}-{model} - {original} - {translated}"

        with self._lock:
            self._buffer.append(line)
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]

            self._rotate_if_needed()
            try:
                self._ensure_file_open()
                if self._file is not None:
                    self._file.write(line + "\n")
                    self._file.flush()
            except OSError:
                pass

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
