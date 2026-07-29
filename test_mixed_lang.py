"""
Tests for mixed-language message splitting and selective translation.
Ensures target-language text is preserved while foreign parts get translated.
"""
from translator import (
    detect_language,
    split_mixed_text,
    _CJK_RE,
    _ALPHA_RE,
)


class TestDetectLanguage:
    def test_detect_english(self):
        assert detect_language("hello world") == "英语"

    def test_detect_chinese(self):
        assert detect_language("你好世界") == "中文"

    def test_detect_german(self):
        assert detect_language("Grüße") == "德语"

    def test_detect_russian(self):
        assert detect_language("привет") == "俄语"

    def test_detect_empty(self):
        assert detect_language("") == "未知"
        assert detect_language("   ") == "未知"


class TestSplitMixedText:
    """split_mixed_text breaks text into (segment, is_target_lang) pairs."""

    def test_pure_foreign_returns_single_segment(self):
        """Pure English → one segment, not in target language."""
        segments = split_mixed_text("hello world", "zh-CN")
        assert len(segments) == 1
        assert segments[0] == ("hello world", False)

    def test_pure_chinese_returns_single_segment(self):
        """Pure Chinese → one segment, is target language."""
        segments = split_mixed_text("你好世界", "zh-CN")
        assert len(segments) == 1
        assert segments[0] == ("你好世界", True)

    def test_mixed_chinese_english_splits_correctly(self):
        """'你好where are you我的朋友' → 3 segments, middle one is foreign."""
        segments = split_mixed_text("你好where are you我的朋友", "zh-CN")
        assert len(segments) == 3
        assert segments[0] == ("你好", True)
        assert segments[1] == ("where are you", False)
        assert segments[2] == ("我的朋友", True)

    def test_alternating_segments(self):
        """Multiple foreign segments embedded in Chinese."""
        segments = split_mixed_text("我hello你world", "zh-CN")
        assert len(segments) == 4
        assert segments[0] == ("我", True)
        assert segments[1] == ("hello", False)
        assert segments[2] == ("你", True)
        assert segments[3] == ("world", False)

    def test_leading_foreign(self):
        """Text starts with foreign language."""
        segments = split_mixed_text("hello你好", "zh-CN")
        assert len(segments) == 2
        assert segments[0] == ("hello", False)
        assert segments[1] == ("你好", True)

    def test_trailing_foreign(self):
        """Text ends with foreign language."""
        segments = split_mixed_text("你好world", "zh-CN")
        assert len(segments) == 2
        assert segments[0] == ("你好", True)
        assert segments[1] == ("world", False)

    def test_only_punctuation_and_numbers(self):
        """Punctuation/numbers between segments are absorbed."""
        segments = split_mixed_text("你好!!!ok???", "zh-CN")
        # "你好!!!" → target-lang context, "ok???" → foreign
        assert len(segments) == 2
        assert segments[1][0].strip() != ""

    def test_empty_string(self):
        assert split_mixed_text("", "zh-CN") == []
        assert split_mixed_text("   ", "zh-CN") == []

    def test_no_chinese_in_text_target_is_chinese(self):
        """Pure English, target=Chinese → all foreign."""
        segments = split_mixed_text("where are you from", "zh-CN")
        assert len(segments) == 1
        assert segments[0] == ("where are you from", False)

    def test_korean_target_korean_kept(self):
        """Target Korean → Korean segments are kept, others translated."""
        segments = split_mixed_text("안녕 hello 안녕", "ko")
        assert len(segments) == 3
        assert segments[0] == ("안녕", True)
        assert segments[1] == ("hello", False)
        assert segments[2] == ("안녕", True)

    def test_japanese_target_japanese_kept(self):
        """Target Japanese → Japanese segments kept."""
        segments = split_mixed_text("こんにちはhello", "ja")
        assert len(segments) == 2
        assert segments[0] == ("こんにちは", True)
        assert segments[1] == ("hello", False)

    def test_russian_target_russian_kept(self):
        """Target Russian → Cyrillic segments kept."""
        segments = split_mixed_text("приветhello", "ru")
        assert len(segments) == 2
        assert segments[0] == ("привет", True)
        assert segments[1] == ("hello", False)


class TestReassemble:
    """Tests for reassembling mixed text after translating foreign segments."""

    def test_reassemble_pure_foreign(self):
        """Pure foreign text is fully translated."""
        segments = [("hello world", False)]
        translations = {"hello world": "你好世界"}
        result = _reassemble(segments, translations)
        assert result == "你好世界"

    def test_reassemble_pure_target(self):
        """Pure target language text stays as-is."""
        segments = [("你好", True)]
        translations = {}
        result = _reassemble(segments, translations)
        assert result == "你好"

    def test_reassemble_mixed(self):
        """Mixed text: target parts kept, foreign parts translated."""
        segments = [
            ("你好", True),
            ("where are you", False),
            ("我的朋友", True),
        ]
        translations = {"where are you": "你在哪里"}
        result = _reassemble(segments, translations)
        assert result == "你好你在哪里我的朋友"

    def test_reassemble_foreign_with_no_translation_falls_back_to_original(self):
        """If a foreign segment has no translation, use the original."""
        segments = [
            ("hello", False),
        ]
        translations = {}  # empty — no translation available
        result = _reassemble(segments, translations)
        assert result == "hello"


def _reassemble(segments, translations):
    """Reassemble segments, replacing foreign parts with their translations."""
    from translator import reassemble_mixed
    return reassemble_mixed(segments, translations)
