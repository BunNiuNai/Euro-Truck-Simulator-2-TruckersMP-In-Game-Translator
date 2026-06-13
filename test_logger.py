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
