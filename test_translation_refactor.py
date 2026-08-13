"""Tests for translation refactor — 对方发消息方式（system+user prompt）+ 动态 max_tokens."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from queue import Queue
from unittest.mock import patch

from config import AppConfig
from translator import Translator, _max_output_tokens


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
