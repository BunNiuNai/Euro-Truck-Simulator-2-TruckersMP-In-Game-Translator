"""Tests for translation refactor — 对方发消息方式（system+user prompt）+ 动态 max_tokens."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from queue import Queue
from unittest.mock import patch, MagicMock

from config import AppConfig
from translator import Translator, _max_output_tokens, _receive_system_prompt


def test_max_output_tokens_clamped():
    assert _max_output_tokens("hi") == 64           # 下界
    assert _max_output_tokens("a" * 1000) == 160    # 上界（单条）
    assert 64 <= _max_output_tokens("hello world") <= 160


def test_receive_prompt_is_system_plus_user():
    cfg = AppConfig()
    cfg.target_language = "zh-CN"
    t = Translator(cfg, Queue(), Queue())

    provider = {
        "endpoint": "https://api.example.com/v1/chat/completions",
        "api_key": "sk-test",
        "model": "test-model",
        "label": "Test",
        "api_format": "openai",
    }

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "你好"}}]}

    with patch("translator.httpx.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.post.return_value = FakeResp()
        result = t._call_provider(provider, "wtf hello")
        payload = mock_client.post.call_args.kwargs["json"]

    assert result == "你好"
    assert payload["temperature"] == 0
    assert payload["messages"][0]["role"] == "system"
    assert "TruckersMP/ETS2" in payload["messages"][0]["content"]
    assert "Map sry=抱歉" in payload["messages"][0]["content"]
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "wtf hello"


def test_deepseek_thinking_disabled():
    cfg = AppConfig()
    cfg.target_language = "zh-CN"
    t = Translator(cfg, Queue(), Queue())

    provider = {
        "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "api_key": "sk-test",
        "model": "deepseek-chat",
        "label": "DeepSeek",
        "api_format": "openai",
    }

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "你好"}}]}

    with patch("translator.httpx.Client") as MockClient:
        mock_client = MockClient.return_value
        mock_client.post.return_value = FakeResp()
        t._call_provider(provider, "hello")
        payload = mock_client.post.call_args.kwargs["json"]

    assert payload.get("thinking") == {"type": "disabled"}


def test_receive_prompt_forbids_explanation():
    system = _receive_system_prompt("zh-CN")
    assert "Translate ONLY" in system
    assert "Never explain" in system
    assert "never analyze" in system
    assert "never quote the original back" in system


def test_batch_split_failure_falls_back_to_individual():
    cfg = AppConfig()
    cfg.target_language = "zh-CN"
    t = Translator(cfg, Queue(), Queue())

    msgs = []
    for text in ["msg1", "msg2", "msg3"]:
        m = MagicMock()
        m.text = text
        m.player_name = "p"
        m.timestamp = "00:00:00"
        m.is_system = False
        msgs.append(m)

    # _call_api 返回一个不含分隔符的整体结果 → 拆分失败
    t._call_api = MagicMock(return_value="one blob without separator")
    t._translate_with_mixed_lang = MagicMock(
        side_effect=lambda text, lang: f"译[{text}]"
    )

    t._flush_llm(msgs)

    # 应逐条回退翻译 3 次
    assert t._translate_with_mixed_lang.call_count == 3


def test_batch_split_success_does_not_fallback():
    cfg = AppConfig()
    cfg.target_language = "zh-CN"
    t = Translator(cfg, Queue(), Queue())

    msgs = []
    for text in ["msg1", "msg2"]:
        m = MagicMock()
        m.text = text
        m.player_name = "p"
        m.timestamp = "00:00:00"
        m.is_system = False
        msgs.append(m)

    # 正确回显分隔符 → 拆分成功，无需回退
    t._call_api = MagicMock(return_value="译1\n---\n译2")
    t._translate_with_mixed_lang = MagicMock()

    t._flush_llm(msgs)

    assert t._translate_with_mixed_lang.call_count == 0


def test_race_skips_untranslated_result():
    cfg = AppConfig()
    cfg.target_language = "zh-CN"
    cfg.llm_providers = [
        {"label": "bad", "model": "m1", "enabled": True, "endpoint": "", "api_key": ""},
        {"label": "good", "model": "m2", "enabled": True, "endpoint": "", "api_key": ""},
    ]
    t = Translator(cfg, Queue(), Queue())

    def fake_call(provider, text):
        if provider["label"] == "bad":
            return text  # 返回原文（未翻译）
        return "好的译文"

    t._call_provider = MagicMock(side_effect=fake_call)

    result, label, model = t._call_api_internal("hello")

    assert result == "好的译文"
    assert label == "good"


def test_race_calls_all_providers_in_parallel():
    import time
    cfg = AppConfig()
    cfg.target_language = "zh-CN"
    cfg.llm_providers = [
        {"label": "a", "model": "m1", "enabled": True, "endpoint": "", "api_key": ""},
        {"label": "b", "model": "m2", "enabled": True, "endpoint": "", "api_key": ""},
    ]
    t = Translator(cfg, Queue(), Queue())

    calls = []

    def fake_call(provider, text):
        calls.append(provider["label"])
        time.sleep(0.05)  # 确保两个 provider 都先被调度
        return "译文"

    t._call_provider = MagicMock(side_effect=fake_call)

    t._call_api_internal("hello")

    # 竞速：所有 provider 都被并行调用，而非只轮转到第一个
    assert set(calls) == {"a", "b"}
