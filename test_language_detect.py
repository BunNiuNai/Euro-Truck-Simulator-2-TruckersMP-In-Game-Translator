"""Tests for language detection."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translator import detect_language


def test_english():
    assert detect_language("hello world how are you") == "英语"

def test_german():
    assert detect_language("Hallo wie geht's dir schön") == "德语"

def test_french():
    assert detect_language("Bonjour ça va bien") == "法语"

def test_spanish():
    assert detect_language("Hola cómo estás") == "西班牙语"

def test_russian():
    assert detect_language("Привет как дела") == "俄语"

def test_japanese():
    assert detect_language("こんにちは元気ですか") == "日语"

def test_korean():
    assert detect_language("안녕하세요") == "韩语"

def test_chinese():
    assert detect_language("你好世界这是一个测试") == "中文"

def test_empty():
    assert detect_language("") == "未知"

def test_whitespace_only():
    assert detect_language("   ") == "未知"

def test_english_common_words():
    assert detect_language("where are you going") == "英语"

def test_portuguese():
    assert detect_language("Olá como vai você não") == "葡萄牙语"

def test_italian():
    assert detect_language("Ciao come stai però") == "意大利语"

def test_thai():
    assert detect_language("สวัสดีครับ") == "泰语"


if __name__ == "__main__":
    for name, fn in sorted(locals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS: {name}")
            except AssertionError as e:
                print(f"FAIL: {name} — {e}")
    print("\n=== LANGUAGE DETECTION TESTS COMPLETE ===")
