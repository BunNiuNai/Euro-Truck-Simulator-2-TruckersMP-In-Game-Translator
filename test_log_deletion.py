"""
Tests for log file deletion functionality.
Reproduces bugs where log deletion silently fails due to open file handles,
uncleared buffers, missing user feedback, and cross-contamination.
"""
import os
import tempfile
import time
from logger import Logger


class TestLogDeletion:
    """Verify delete_all_logs correctly handles file locks and buffer state."""

    def _make_logger(self, tmpdir: str) -> Logger:
        """Create a Logger writing to a temp directory."""
        return Logger(log_dir=tmpdir, max_files=7, max_size=1024, buffer_size=100)

    def _write_log_entries(self, logger: Logger, n: int = 3) -> None:
        """Write a few log entries to create log files."""
        for i in range(n):
            logger.info("TEST", f"test message {i}")

    def test_delete_clears_current_file(self):
        """Bug 1: Current log file is held open → os.remove fails silently on Windows.
        Fix: Logger must close its file handle before deleting the current file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            self._write_log_entries(logger)

            # The current translator log file should now exist
            files_before = [f for f in os.listdir(tmpdir) if f.endswith(".log")]
            assert len(files_before) >= 1, f"Expected at least 1 log file, got {files_before}"

            # Delete — this should succeed even for the currently-open file
            deleted = logger.delete_all_logs()
            assert deleted >= 1, f"Expected at least 1 file deleted, got {deleted}"

            # Verify files are actually gone from disk
            files_after = [f for f in os.listdir(tmpdir) if f.endswith(".log")]
            assert len(files_after) == 0, \
                f"Expected 0 log files after deletion, got {files_after}"

    def test_delete_clears_in_memory_buffer(self):
        """Bug 2: After file deletion, the in-memory buffer is NOT cleared.
        _refresh_logs() reads from buffer → UI shows stale entries even though
        files are gone.
        Fix: delete_all_logs must clear the buffer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            self._write_log_entries(logger)

            # Buffer should have entries before deletion
            before_buffer = logger.get_recent()
            assert len(before_buffer) > 0, \
                f"Expected buffer entries before deletion, got {len(before_buffer)}"

            logger.delete_all_logs()

            # Buffer should be empty after deletion
            after_buffer = logger.get_recent()
            assert len(after_buffer) == 0, \
                f"Expected empty buffer after deletion, got {len(after_buffer)} lines"

    def test_delete_returns_accurate_count(self):
        """Bug 3: delete_all_logs returns a count, but the caller never shows it.
        The count must be accurate so we can display it to the user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            self._write_log_entries(logger)

            # Also create a rotated file to test multi-file deletion
            rotated_path = os.path.join(tmpdir, "translator_2026-01-01_1.log")
            with open(rotated_path, "w") as f:
                f.write("old log entry\n")

            deleted = logger.delete_all_logs()

            # Count includes both current + rotated files
            assert deleted == 2, \
                f"Expected 2 deleted files (current + rotated), got {deleted}"

    def test_delete_only_affects_log_files(self):
        """Safety: delete_all_logs must NOT touch non-log files in the directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            self._write_log_entries(logger)

            # Create a non-log file
            config_path = os.path.join(tmpdir, "config.json")
            with open(config_path, "w") as f:
                f.write('{"key": "value"}')

            logger.delete_all_logs()

            # Non-log files must survive
            assert os.path.exists(config_path), \
                "Non-log file was deleted — delete_all_logs is too aggressive"

    def test_logger_reopens_file_after_delete(self):
        """After deletion, the Logger should be able to continue writing logs
        without errors (file handle is lazily re-opened on next write)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            self._write_log_entries(logger)

            logger.delete_all_logs()

            # Should NOT raise — Logger lazily reopens file for new writes
            logger.info("TEST", "post-deletion message")

            # Verify the new log file exists and has our message
            files = [f for f in os.listdir(tmpdir) if f.endswith(".log")]
            assert len(files) == 1, \
                f"Expected 1 new log file after post-deletion write, got {files}"
            assert logger._file is not None, \
                "Logger file handle should be re-opened after write"

            # Close before tempdir cleanup, or Windows will block rmtree
            logger.close()


class TestTranslationLog:
    """Verify the unified translation_log() method."""

    def _make_logger(self, tmpdir: str) -> Logger:
        return Logger(log_dir=tmpdir, max_files=7, max_size=1024, buffer_size=100)

    def test_translation_log_writes_unified_format(self):
        """translation_log() writes to the unified translator_*.log file
        in format: YYYY-MM-DD HH:MM:SS - provider-model - original - translated"""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            logger.translation_log("OpenAI", "gpt-4o", "Hello", "你好")

            files = [f for f in os.listdir(tmpdir) if f.startswith("translator_")]
            assert len(files) >= 1, f"Expected translator log file, got {files}"

            filepath = os.path.join(tmpdir, files[0])
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            assert " - OpenAI-gpt-4o - Hello - 你好" in content, \
                f"Unexpected log format: {content}"

            # Close before tempdir cleanup, or Windows will block rmtree
            logger.close()

    def test_delete_all_logs_deletes_everything(self):
        """After merging, delete_all_logs() removes all translator_*.log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = self._make_logger(tmpdir)
            logger.info("TEST", "system message")
            logger.translation_log("OpenAI", "gpt-4o", "Hi", "嗨")

            files_before = [f for f in os.listdir(tmpdir) if f.endswith(".log")]
            assert len(files_before) >= 1

            deleted = logger.delete_all_logs()
            assert deleted >= 1

            files_after = [f for f in os.listdir(tmpdir) if f.endswith(".log")]
            assert len(files_after) == 0
