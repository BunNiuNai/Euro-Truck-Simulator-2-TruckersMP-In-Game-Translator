"""Tests for chat_dictionary — 五层术语处理."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chat_dictionary import (
    SLANG_TOKENS,
    ETS2_TERMS,
    short_phrase_fallback,
    fix_leftover_shorthand,
    preserve_mention_prefix,
    looks_untranslated,
    guess_source_language,
    is_non_translatable,
)


# ── 第1层：俚语 token 词典 ──

def test_slang_token_hit():
    assert short_phrase_fallback("wtf") == "什么鬼"
    assert short_phrase_fallback("sry") == "抱歉"
    assert short_phrase_fallback("rec") == "已录屏"
    assert short_phrase_fallback("ram") == "撞人"


def test_slang_token_miss_returns_empty():
    # 长句需要 LLM，本地字典应返回空串
    assert short_phrase_fallback("this is a long sentence that needs llm") == ""


# ── 第2层：完整短语精确匹配 ──

def test_phrase_fallback():
    assert short_phrase_fallback("rec ban") == "已录屏，等封禁"
    assert short_phrase_fallback("thank you") == "谢谢"


def test_multilingual_phrase():
    assert short_phrase_fallback("gute reise") == "一路顺风"
    assert short_phrase_fallback("сам виноват") == "是你自己的错"


# ── 第3层：结构化短语 ──

def test_structured_phrase_with_name():
    assert short_phrase_fallback("report someplayer") == "举报 someplayer"


# ── ETS2 词汇保留 ──

def test_ets2_term_present():
    assert ETS2_TERMS["truck"] == "卡车"
    assert ETS2_TERMS["trailer"] == "挂车"
    assert ETS2_TERMS["convoy"] == "车队"


def test_ets2_term_single_word_hit():
    assert short_phrase_fallback("truck") == "卡车"
    assert short_phrase_fallback("convoy") == "车队"


def test_ets2_term_multiword_hit():
    assert short_phrase_fallback("gas station") == "加油站"
    assert short_phrase_fallback("speed limit") == "限速"


# ── 第5层：后处理补译 ──

def test_fix_leftover_shorthand():
    # LLM 返回残留 "wtf" 未翻译
    assert "什么鬼" in fix_leftover_shorthand("wtf 你在干嘛")


# ── @mention 保留 ──

def test_preserve_mention_prefix():
    assert preserve_mention_prefix("@Player123 hello", "你好") == "@Player123 你好"


# ── 未翻译校验 ──

def test_looks_untranslated_zh_target():
    assert looks_untranslated("hello world", "hello world", "zh-CN") is True
    assert looks_untranslated("hello world", "你好世界", "zh-CN") is False


# ── 源语言检测 ──

def test_guess_source_language():
    assert guess_source_language("привет как дела") == "ru"
    assert guess_source_language("merhaba nasılsın") == "tr"
    assert guess_source_language("hello there") == "en"


def test_is_non_translatable():
    # 纯标点/数字/空串 → 无需翻译
    assert is_non_translatable(".") is True
    assert is_non_translatable("...") is True
    assert is_non_translatable("123") is True
    assert is_non_translatable("") is True
    assert is_non_translatable("!?") is True
    # 含字母 → 需要翻译
    assert is_non_translatable("hello") is False
    assert is_non_translatable("你好") is False
    assert is_non_translatable("1 sec") is False
