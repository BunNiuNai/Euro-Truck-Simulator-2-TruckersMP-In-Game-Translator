"""Verify config provider migration and encryption."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    AppConfig, ProviderConfig, load_config, save_config,
    _maybe_encrypt, _maybe_decrypt, _SECRET_FIELDS,
)

def test_provider_config_default():
    p = ProviderConfig()
    assert p.label == ""
    assert p.endpoint == ""
    assert p.api_key == ""
    assert p.model == ""
    assert p.enabled == True
    print("PASS: ProviderConfig defaults")

def test_appconfig_providers_field():
    cfg = AppConfig()
    assert cfg.llm_providers == []
    print("PASS: AppConfig llm_providers field")

def test_migration_from_old_fields():
    tmpd = tempfile.mkdtemp(prefix="ets2_cfg_test_")
    tmpcfg = os.path.join(tmpd, "config.json")

    old_data = {
        "api_endpoint": "https://api.test.com/v1/chat/completions",
        "api_key": "sk-test123",
        "api_model": "test-model",
        "llm_providers": []
    }
    with open(tmpcfg, "w", encoding="utf-8") as f:
        json.dump(old_data, f)

    import config as cfg_module
    orig_path = cfg_module.CONFIG_PATH
    orig_dir = cfg_module.CONFIG_DIR
    cfg_module.CONFIG_PATH = tmpcfg
    cfg_module.CONFIG_DIR = tmpd
    try:
        result = load_config()
        assert len(result.llm_providers) == 1, f"Expected 1 provider, got {len(result.llm_providers)}"
        p = result.llm_providers[0]
        assert p["label"] == "LLM Provider"
        assert p["endpoint"] == "https://api.test.com/v1/chat/completions"
        assert p["api_key"] == "sk-test123"
        assert p["model"] == "test-model"
        assert p["enabled"] == True
        print("PASS: migration from old fields")
    finally:
        cfg_module.CONFIG_PATH = orig_path
        cfg_module.CONFIG_DIR = orig_dir
        import shutil
        shutil.rmtree(tmpd, ignore_errors=True)

def test_provider_api_key_encrypted():
    p = ProviderConfig(
        label="Test", endpoint="https://api.test.com",
        api_key="sk-secret-123", model="test",
    )
    enc = _maybe_encrypt("api_key", p.api_key)
    assert enc.startswith("dpapi:"), f"Expected dpapi: prefix, got {enc[:20]}"
    dec = _maybe_decrypt("api_key", enc)
    assert dec == "sk-secret-123", f"Round-trip failed: {dec}"
    print("PASS: provider api_key encryption round-trip")

def test_multiple_providers_save_load():
    tmpd = tempfile.mkdtemp(prefix="ets2_cfg_test_")
    tmpcfg = os.path.join(tmpd, "config.json")

    cfg = AppConfig()
    cfg.llm_providers = [
        {"label": "DeepSeek", "endpoint": "https://api.deepseek.com/v1/chat/completions",
         "api_key": "sk-aaa", "model": "deepseek-chat", "enabled": True},
        {"label": "Qwen", "endpoint": "https://api.siliconflow.cn/v1/chat/completions",
         "api_key": "sk-bbb", "model": "Qwen/Qwen3-8B", "enabled": True},
    ]

    import config as cfg_module
    orig_path = cfg_module.CONFIG_PATH
    orig_dir = cfg_module.CONFIG_DIR
    cfg_module.CONFIG_PATH = tmpcfg
    cfg_module.CONFIG_DIR = tmpd
    try:
        save_config(cfg)
        loaded = load_config()
        assert len(loaded.llm_providers) == 2
        assert loaded.llm_providers[0]["label"] == "DeepSeek"
        assert loaded.llm_providers[1]["label"] == "Qwen"
        assert loaded.llm_providers[0]["api_key"] == "sk-aaa"
        print("PASS: multiple providers save/load")
    finally:
        cfg_module.CONFIG_PATH = orig_path
        cfg_module.CONFIG_DIR = orig_dir
        import shutil
        shutil.rmtree(tmpd, ignore_errors=True)

if __name__ == "__main__":
    test_provider_config_default()
    test_appconfig_providers_field()
    test_migration_from_old_fields()
    test_provider_api_key_encrypted()
    test_multiple_providers_save_load()
    print("\n=== ALL PROVIDER CONFIG TESTS PASSED ===")
