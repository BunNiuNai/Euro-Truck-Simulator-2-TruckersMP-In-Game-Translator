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
        self.log_path = os.path.join(self.tmpdir, "chat_2026_06_23_log.txt")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _append_line(self, channel, time_str, player, text):
        line = f"[{channel}] [{time_str}] {player} (A 123): {text}\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(line)

    def test_match_found(self):
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
        import threading
        result_holder = []

        def do_confirm():
            result_holder.append(
                self.sender._wait_confirmation("hello world", timeout=2.0, log_path=self.log_path)
            )

        t = threading.Thread(target=do_confirm, daemon=True)
        t.start()
        time.sleep(0.15)
        self._append_line("Global", "12:00:00", "TestPlayer", "hello world")
        time.sleep(0.2)
        self._append_line("Global", "12:00:01", "OtherPlayer", "hello world")
        t.join(timeout=3.0)
        assert result_holder[0] is True

    def test_normalized_match(self):
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
        self._append_line("Global", "11:00:00", "OldPlayer", "hello world")
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
