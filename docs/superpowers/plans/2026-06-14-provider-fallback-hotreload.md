# Provider Fallback + Hot-Reload + Speed Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Multi-LLM provider parallel-race + fallback, config hot-reload, batch window 0.3s, HTTP timeout 8s, LRU cache 1000.

**Architecture:** Config gets `llm_providers` list with backward-compatible migration from old single-api fields. Translator uses ThreadPoolExecutor for parallel provider race, falls back to serial retry. Hot-reload checks config mtime every 3 seconds in the message loop. Settings UI gets provider list with add/remove/reorder.

**Tech Stack:** Python 3.10+, dataclasses, concurrent.futures, httpx, tkinter

---

## File Structure Map

| File | Action | Responsibility |
|:---|:---|:---|
| `config.py` | Modify | ProviderConfig dataclass, llm_providers field, migration, encryption |
| `translator.py` | Modify | Parallel race, fast timeout, big cache, short window, hot-reload, fallback |
| `main.py` | Modify | Settings UI: provider list add/edit/delete/reorder, test-all |

---

### Task 1: config.py — ProviderConfig + migration + encryption

**Files:**
- Modify: `config.py`
- Create: `test_provider_config.py`

- [ ] **Step 1: Write verification script**

```python
# test_provider_config.py
"""Verify config provider migration and encryption."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    AppConfig, ProviderConfig, load_config, save_config,
    _maybe_encrypt, _maybe_decrypt, _SECRET_FIELDS,
    CONFIG_PATH, CONFIG_DIR,
)

def test_provider_config_default():
    """ProviderConfig has correct defaults."""
    p = ProviderConfig()
    assert p.label == ""
    assert p.endpoint == ""
    assert p.api_key == ""
    assert p.model == ""
    assert p.enabled == True
    print("PASS: ProviderConfig defaults")

def test_appconfig_providers_field():
    """AppConfig has llm_providers field."""
    cfg = AppConfig()
    assert cfg.llm_providers == []
    print("PASS: AppConfig llm_providers field")

def test_migration_from_old_fields():
    """Old api_endpoint/api_key/api_model migrate to llm_providers[0]."""
    import json, os
    tmpd = tempfile.mkdtemp(prefix="ets2_cfg_test_")
    tmpcfg = os.path.join(tmpd, "config.json")
    
    # Write old-style config
    old_data = {
        "api_endpoint": "https://api.test.com/v1/chat/completions",
        "api_key": "sk-test123",
        "api_model": "test-model",
        "llm_providers": []
    }
    with open(tmpcfg, "w", encoding="utf-8") as f:
        json.dump(old_data, f)
    
    # Patch CONFIG_PATH to test path
    import config as cfg_module
    orig_path = cfg_module.CONFIG_PATH
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
        cfg_module.CONFIG_DIR = os.path.dirname(orig_path)
        import shutil
        shutil.rmtree(tmpd, ignore_errors=True)

def test_provider_api_key_encrypted():
    """Provider api_key gets encrypted on save."""
    p = ProviderConfig(
        label="Test",
        endpoint="https://api.test.com",
        api_key="sk-secret-123",
        model="test",
    )
    enc = _maybe_encrypt("api_key", p.api_key)
    assert enc.startswith("dpapi:"), f"Expected dpapi: prefix, got {enc[:20]}"
    dec = _maybe_decrypt("api_key", enc)
    assert dec == "sk-secret-123", f"Round-trip failed: {dec}"
    print("PASS: provider api_key encryption round-trip")

def test_multiple_providers_save_load():
    """Multiple providers survive save/load round-trip."""
    import json, os
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
```

- [ ] **Step 2: Run test (expect fail)**

```bash
cd "y:/翻译器项目/ets2-translator" && python test_provider_config.py
```
Expected: `AttributeError: 'AppConfig' object has no attribute 'llm_providers'`

- [ ] **Step 3: Implement config.py changes**

Add `ProviderConfig` dataclass after imports:

```python
@dataclass
class ProviderConfig:
    """A single LLM provider configuration."""
    label: str = ""
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True
```

Add `llm_providers` to `AppConfig` (after `api_model`):

```python
@dataclass
class AppConfig:
    api_endpoint: str = ""
    api_key: str = ""
    api_model: str = ""
    llm_providers: list[dict] = field(default_factory=list)  # NEW: list of provider dicts
    target_language: str = "zh-CN"
    # ... rest unchanged ...
```

Note: need `from dataclasses import dataclass, asdict, field` at top (add `field` to existing import).

Update `_SECRET_FIELDS` to include provider api_keys only on save/load (not as a flat field since llm_providers is a list):

After existing `_SECRET_FIELDS = {"api_key", "baidu_secret"}`:

In `load_config()`, after decrypting flat fields, also decrypt each provider's api_key:

```python
# Decrypt sensitive fields in providers
for provider in merged.get("llm_providers", []):
    if "api_key" in provider and isinstance(provider["api_key"], str):
        provider["api_key"] = _maybe_decrypt("api_key", provider["api_key"])
```

And migration from old fields. After the merge:

```python
# Migration: if llm_providers is empty but old api_endpoint is set, create one provider
if not merged.get("llm_providers") and merged.get("api_endpoint"):
    merged["llm_providers"] = [{
        "label": "LLM Provider",
        "endpoint": merged["api_endpoint"],
        "api_key": merged["api_key"],
        "model": merged["api_model"],
        "enabled": True,
    }]
```

In `save_config()`, after encrypting flat fields, also encrypt each provider's api_key:

```python
# Encrypt sensitive fields in providers
for provider in data.get("llm_providers", []):
    if "api_key" in provider and isinstance(provider["api_key"], str):
        provider["api_key"] = _maybe_encrypt("api_key", provider["api_key"])
```

Also sync first provider to old flat fields:

```python
# Sync first provider to legacy flat fields for backward compat
if data.get("llm_providers"):
    first = data["llm_providers"][0]
    data["api_endpoint"] = first.get("endpoint", "")
    data["api_key"] = first.get("api_key", "")
    data["api_model"] = first.get("model", "")
```

Update `from dataclasses import dataclass, asdict` to `from dataclasses import dataclass, asdict, field`.

- [ ] **Step 4: Run test (expect pass)**

```bash
cd "y:/翻译器项目/ets2-translator" && python test_provider_config.py
```
Expected: `=== ALL PROVIDER CONFIG TESTS PASSED ===`

- [ ] **Step 5: Commit**

```bash
cd "y:/翻译器项目/ets2-translator"
git add config.py test_provider_config.py
git commit -m "feat: add llm_providers config with migration and encryption"
```

---

### Task 2: translator.py — Speed optimizations + parallel race + hot-reload

**Files:**
- Modify: `translator.py`

- [ ] **Step 1: Change speed constants**

In `translator.py`, update constants:

```python
CACHE_SIZE = 1000       # was 200
BATCH_WINDOW = 0.3      # was 0.8
```

Change HTTP timeout in `Translator.__init__`:

```python
self._client = httpx.Client(timeout=8.0)  # was 30.0
```

And in `translate_to_english()`:

```python
resp = httpx.post(endpoint, json=payload, headers=headers, timeout=8.0)  # was 30.0
```

And in `test_connection()`:

```python
client = httpx.Client(timeout=8.0)  # was 15.0
```

- [ ] **Step 2: Implement parallel provider race in _call_api**

Replace the single `_call_api` with per-provider versions:

```python
def _call_provider(self, provider: dict, text: str) -> str:
    """Call a single LLM provider. Raises exception on failure."""
    endpoint = provider["endpoint"].strip()
    if not endpoint.startswith(("http://", "https://")):
        endpoint = "https://" + endpoint

    payload = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": self.cfg.system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 500 if BATCH_SEPARATOR not in text else 500 * text.count(BATCH_SEPARATOR) + 500,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {provider['api_key']}",
    }

    resp = self._client.post(endpoint, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _call_api(self, text: str) -> str:
    """Call providers with parallel race + serial fallback."""
    if self._should_skip(text):
        return text

    providers = [p for p in self.cfg.llm_providers if p.get("enabled", True)]
    if not providers:
        # Fallback to legacy single-API mode
        return self._call_api_legacy(text)

    log = get_logger()

    # Round 1: Parallel race
    errors = []
    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = {
            executor.submit(self._call_provider, p, text): p["label"]
            for p in providers
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                if log:
                    log.info("LLM", f"竞速成功: {label}")
                return result
            except Exception as e:
                err = self._format_error(e)
                errors.append(f"{label}: {err}")
                if log:
                    log.warn("LLM", f"竞速失败: {label} - {err}")

    # Round 2: Serial retry (180ms apart)
    if log:
        log.warn("LLM", f"第一轮全部失败，进入串行重试 ({len(providers)} providers)")
    import time
    for p in providers:
        try:
            result = self._call_provider(p, text)
            if log:
                log.info("LLM", f"重试成功: {p['label']}")
            return result
        except Exception as e:
            time.sleep(0.18)

    # All failed
    raise Exception(" | ".join(errors) if errors else "所有 Provider 翻译失败")


def _call_api_legacy(self, text: str) -> str:
    """Legacy single-API call (used when llm_providers is empty)."""
    payload = {
        "model": self.cfg.api_model,
        "messages": [
            {"role": "system", "content": self.cfg.system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 500 if BATCH_SEPARATOR not in text else 500 * text.count(BATCH_SEPARATOR) + 500,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.cfg.api_key}",
    }
    resp = self._client.post(self.cfg.api_endpoint, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()
```

- [ ] **Step 3: Add hot-reload in Translator.run()**

In `Translator.run()`, add a config mtime check every 3 seconds. After the `while not self._stop_event.is_set():` line:

```python
def run(self):
    import os
    from config import load_config, CONFIG_PATH
    batch = []
    batch_deadline = None
    _last_config_mtime = os.path.getmtime(CONFIG_PATH) if os.path.exists(CONFIG_PATH) else 0
    _config_check_time = time.monotonic()

    while not self._stop_event.is_set():
        # Hot-reload: check config every 3 seconds
        now = time.monotonic()
        if now - _config_check_time > 3.0:
            _config_check_time = now
            try:
                mtime = os.path.getmtime(CONFIG_PATH)
                if mtime != _last_config_mtime:
                    _last_config_mtime = mtime
                    self.cfg = load_config()
                    self._client.close()
                    self._client = httpx.Client(timeout=8.0)
                    log = get_logger()
                    if log:
                        log.info("SYS", "配置已热重载")
            except OSError:
                pass

        # ... rest of existing message loop unchanged ...
```

- [ ] **Step 4: Update translate_to_english() for multi-provider**

In `translate_to_english()`, use providers:

```python
def translate_to_english(cfg: AppConfig, text: str) -> str:
    if cfg.translation_backend == "baidu":
        return translate_to_english_via_baidu(cfg.baidu_appid, cfg.baidu_secret, text)

    # Use multi-provider if available
    providers = [p for p in cfg.llm_providers if p.get("enabled", True)]
    if providers:
        # Parallel race for send translation
        from concurrent.futures import ThreadPoolExecutor, as_completed
        errors = []
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            def _call_one(p):
                ep = p["endpoint"].strip()
                if not ep.startswith(("http://", "https://")):
                    ep = "https://" + ep
                payload = {
                    "model": p["model"],
                    "messages": [
                        {"role": "system", "content": SEND_SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 300,
                }
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {p['api_key']}",
                }
                resp = httpx.post(ep, json=payload, headers=headers, timeout=8.0)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()

            futures = {executor.submit(_call_one, p): p["label"] for p in providers}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    # Hybrid mode: Baidu verify
                    if cfg.translation_backend == "llm+baidu" and cfg.baidu_appid and cfg.baidu_secret:
                        try:
                            baidu_result = translate_to_english_via_baidu(cfg.baidu_appid, cfg.baidu_secret, text)
                            if _translations_differ(result, baidu_result):
                                return baidu_result
                        except Exception:
                            pass
                    return result
                except Exception as e:
                    errors.append(str(e))

        raise Exception(" | ".join(errors) if errors else "所有 Provider 翻译失败")

    # Legacy single-API fallback
    # ... existing code for cfg.api_endpoint/cfg.api_key/cfg.api_model ...
```

- [ ] **Step 5: Keep batch translation using first provider's _call_api**

The batch `_flush_llm()` already calls `self._call_api()` which now handles multi-provider. No change needed in `_flush_llm()`, `_flush_baidu()`, or `_flush_hybrid()`.

- [ ] **Step 6: Verify**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from config import AppConfig, load_config
from translator import Translator, CACHE_SIZE, BATCH_WINDOW
assert CACHE_SIZE == 1000, f'CACHE_SIZE={CACHE_SIZE}'
assert BATCH_WINDOW == 0.3, f'BATCH_WINDOW={BATCH_WINDOW}'
cfg = AppConfig()
# Test legacy mode still works
cfg.api_endpoint = 'https://api.test.com/v1'
cfg.api_key = 'sk-test'
cfg.api_model = 'test'
print('translator constants OK')
print('legacy mode import OK')
"
```

- [ ] **Step 7: Commit**

```bash
cd "y:/翻译器项目/ets2-translator"
git add translator.py
git commit -m "feat: parallel provider race, speed optimizations, hot-reload"
```

---

### Task 3: main.py — Settings UI provider list

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Replace API tab with provider list UI**

In `_build_api_tab()`, replace the Card 1 content. Instead of single endpoint/key/model fields, build a scrollable provider list:

```python
def _build_api_tab(self):
    frame = self._tab_frames["api"] = tk.Frame(self._content_area, bg=self._PAGE_BG)
    frame.columnconfigure(0, weight=1)

    canvas = tk.Canvas(frame, bg=self._PAGE_BG, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)

    inner = tk.Frame(canvas, bg=self._PAGE_BG, padx=20, pady=16)
    inner.columnconfigure(0, weight=1)
    inner_id = canvas.create_window((0, 0), window=inner, anchor=tk.NW)

    def _on_inner_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_inner_configure)

    def _on_canvas_configure(event):
        canvas.itemconfig(inner_id, width=event.width)
    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # LLM Providers section
    self._section_label(inner, "LLM PROVIDERS  /  翻译提供商").pack(fill=tk.X, pady=(0, 8))

    # Provider list container
    self._provider_list_frame = tk.Frame(inner, bg=self._PAGE_BG)
    self._provider_list_frame.pack(fill=tk.X, pady=(0, 8))
    self._provider_list_frame.columnconfigure(0, weight=1)

    # Add provider button
    add_btn = tk.Label(inner, text="+ 添加 Provider", bg=self._CARD_BG, fg=self._ACCENT,
                       font=("Microsoft YaHei", 10), padx=16, pady=6, cursor="hand2",
                       anchor=tk.CENTER)
    add_btn.pack(fill=tk.X, pady=(0, 12))
    add_btn.bind("<Button-1>", lambda e: self._add_provider())
    add_btn.bind("<Enter>", lambda e: add_btn.configure(bg="#21262d"))
    add_btn.bind("<Leave>", lambda e: add_btn.configure(bg=self._CARD_BG))

    # Baidu section
    self._section_label(inner, "BAIDU TRANSLATE / 百度翻译（可选监督）").pack(fill=tk.X, pady=(12, 8))
    card_baidu = self._card(inner, padx=16, pady=12)
    card_baidu.pack(fill=tk.X, pady=(0, 4))
    card_baidu.columnconfigure(1, weight=1)

    bd = 0
    self.baidu_appid_entry = self._entry(card_baidu, width=42)
    bd = self._row(card_baidu, bd, "APP ID", self.baidu_appid_entry)

    self.baidu_secret_entry = self._entry(card_baidu, show="*", width=42)
    bd = self._row(card_baidu, bd, "Secret / 密钥", self.baidu_secret_entry)

    tk.Label(card_baidu,
             text="免费申请 fanyi-api.baidu.com · 标准版每月 500 万字符",
             bg=self._CARD_BG, fg=self._TEXT_SEC,
             font=("Microsoft YaHei", 7)).grid(
        row=bd, column=0, columnspan=2, sticky=tk.W, padx=16, pady=(2, 12))

    # Test button
    btn_row = tk.Frame(inner, bg=self._PAGE_BG)
    btn_row.pack(fill=tk.X, pady=(16, 8))

    self._test_btn = self._pill_btn(btn_row, "Test All / 测试全部", self._test_all_providers, accent=False)
    self._test_btn.pack(side=tk.LEFT, padx=(0, 8))

    self._test_status = tk.Label(btn_row, text="", bg=self._PAGE_BG, fg=self._TEXT_SEC,
                                  font=("Microsoft YaHei", 9), anchor=tk.W)
    self._test_status.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

    # Build provider widgets
    self._provider_widgets = []
    self._rebuild_provider_list()
```

- [ ] **Step 2: Add provider management methods**

```python
def _rebuild_provider_list(self):
    """Rebuild provider widgets from cfg.llm_providers."""
    # Clear existing
    for w in self._provider_widgets:
        w["frame"].destroy()
    self._provider_widgets.clear()

    for i, p in enumerate(self.cfg.llm_providers):
        self._add_provider_widget(i, p)

def _add_provider_widget(self, index, p):
    """Create a widget for one provider."""
    card = self._card(self._provider_list_frame, padx=12, pady=8)
    card.grid(row=index, column=0, sticky="ew", pady=(0, 4))
    card.columnconfigure(1, weight=1)

    # Row 0: label + enabled + buttons
    header = tk.Frame(card, bg=self._CARD_BG)
    header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))
    header.columnconfigure(1, weight=1)

    en_var = tk.BooleanVar(value=p.get("enabled", True))
    cb = tk.Checkbutton(header, text=p.get("label", f"Provider {index+1}"),
                        variable=en_var, bg=self._CARD_BG, fg=self._TEXT,
                        font=("Microsoft YaHei", 10, "bold"),
                        selectcolor=self._CARD_BG,
                        activebackground=self._CARD_BG,
                        activeforeground=self._ACCENT,
                        command=lambda i=index, v=en_var: self._toggle_provider(i, v.get()))
    cb.pack(side=tk.LEFT)

    # Move up/down/delete buttons
    btn_frame = tk.Frame(header, bg=self._CARD_BG)
    btn_frame.pack(side=tk.RIGHT)
    for text, cmd in [("↑", lambda i=index: self._move_provider(i, -1)),
                       ("↓", lambda i=index: self._move_provider(i, 1)),
                       ("✕", lambda i=index: self._remove_provider(i))]:
        lb = tk.Label(btn_frame, text=text, bg=self._CARD_BG, fg=self._TEXT_SEC,
                     font=("Microsoft YaHei", 9), padx=4, cursor="hand2")
        lb.pack(side=tk.LEFT)
        lb.bind("<Button-1>", lambda e, c=cmd: c())
        lb.bind("<Enter>", lambda e, l=lb: l.configure(fg=self._ACCENT))
        lb.bind("<Leave>", lambda e, l=lb: l.configure(fg=self._TEXT_SEC))

    # Label
    r = 1
    self._label(card, "Label / 名称").grid(row=r, column=0, sticky=tk.W, padx=(16, 8), pady=3)
    label_entry = self._entry(card, width=36)
    label_entry.insert(0, p.get("label", ""))
    label_entry.grid(row=r, column=1, sticky=tk.EW, padx=(0, 12), pady=3)
    r += 1

    # Endpoint
    self._label(card, "Endpoint / 地址").grid(row=r, column=0, sticky=tk.W, padx=(16, 8), pady=3)
    ep_entry = self._entry(card, width=36)
    ep_entry.insert(0, p.get("endpoint", ""))
    ep_entry.grid(row=r, column=1, sticky=tk.EW, padx=(0, 12), pady=3)
    r += 1

    # API Key
    self._label(card, "API Key / 密钥").grid(row=r, column=0, sticky=tk.W, padx=(16, 8), pady=3)
    key_entry = self._entry(card, show="*", width=36)
    key_entry.insert(0, p.get("api_key", ""))
    key_entry.grid(row=r, column=1, sticky=tk.EW, padx=(0, 12), pady=3)
    r += 1

    # Model
    self._label(card, "Model / 模型").grid(row=r, column=0, sticky=tk.W, padx=(16, 8), pady=3)
    model_entry = self._entry(card, width=36)
    model_entry.insert(0, p.get("model", ""))
    model_entry.grid(row=r, column=1, sticky=tk.EW, padx=(0, 12), pady=3)

    self._provider_widgets.append({
        "frame": card,
        "enabled_var": en_var,
        "label_entry": label_entry,
        "ep_entry": ep_entry,
        "key_entry": key_entry,
        "model_entry": model_entry,
    })

def _add_provider(self):
    """Add a new provider to the list."""
    self.cfg.llm_providers.append({
        "label": f"Provider {len(self.cfg.llm_providers) + 1}",
        "endpoint": "",
        "api_key": "",
        "model": "",
        "enabled": True,
    })
    self._rebuild_provider_list()

def _remove_provider(self, index):
    if 0 <= index < len(self.cfg.llm_providers):
        del self.cfg.llm_providers[index]
        self._rebuild_provider_list()

def _move_provider(self, index, direction):
    new_idx = index + direction
    if 0 <= new_idx < len(self.cfg.llm_providers):
        self.cfg.llm_providers[index], self.cfg.llm_providers[new_idx] = \
            self.cfg.llm_providers[new_idx], self.cfg.llm_providers[index]
        self._rebuild_provider_list()

def _toggle_provider(self, index, enabled):
    if 0 <= index < len(self.cfg.llm_providers):
        self.cfg.llm_providers[index]["enabled"] = enabled

def _gather_providers(self):
    """Read provider values from UI widgets back into cfg."""
    for i, w in enumerate(self._provider_widgets):
        if i < len(self.cfg.llm_providers):
            self.cfg.llm_providers[i]["label"] = w["label_entry"].get().strip()
            self.cfg.llm_providers[i]["endpoint"] = w["ep_entry"].get().strip()
            self.cfg.llm_providers[i]["api_key"] = w["key_entry"].get().strip()
            self.cfg.llm_providers[i]["model"] = w["model_entry"].get().strip()

def _test_all_providers(self):
    """Test connectivity for all enabled providers + Baidu."""
    self._gather_providers()
    self._test_status.config(text="正在测试...", fg=self._TEXT_SEC)
    self._test_btn.configure(state=tk.DISABLED)

    def run_test():
        results = []
        for p in self.cfg.llm_providers:
            if p.get("enabled", True):
                ok, msg = test_connection(p["endpoint"], p["api_key"], p["model"])
                results.append(f"{p['label']}: {'✓' if ok else '✗'} {msg}")
        # Also test Baidu if configured
        if self.cfg.baidu_appid and self.cfg.baidu_secret:
            ok, msg = test_baidu_connection(self.cfg.baidu_appid, self.cfg.baidu_secret)
            results.append(f"百度: {'✓' if ok else '✗'} {msg}")
        self.top.after(0, lambda: self._on_test_result(
            all("✓" in r for r in results),
            "\n".join(results)
        ))

    threading.Thread(target=run_test, daemon=True).start()
```

- [ ] **Step 3: Update _load_values() for provider list**

```python
def _load_values(self):
    # ... keep existing Baidu, lang, etc loads ...
    self.baidu_appid_entry.insert(0, self.cfg.baidu_appid)
    self.baidu_secret_entry.insert(0, self.cfg.baidu_secret)
    self.lang_var.set(self.cfg.target_language)
    self._rebuild_provider_list()
```

- [ ] **Step 4: Update _save() for provider list**

In `_save()`, before creating result:

```python
def _save(self):
    self._gather_providers()  # ADD THIS LINE
    self.result = AppConfig(
        llm_providers=self.cfg.llm_providers,  # ADD THIS LINE
        api_endpoint=self.cfg.llm_providers[0]["endpoint"] if self.cfg.llm_providers else "",  # ADD
        api_key=self.cfg.llm_providers[0]["api_key"] if self.cfg.llm_providers else "",  # ADD
        api_model=self.cfg.llm_providers[0]["model"] if self.cfg.llm_providers else "",  # ADD
        system_prompt=self.cfg.system_prompt,
        # ... rest unchanged ...
    )
```

- [ ] **Step 5: Verify imports**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "import main; print('main.py OK')"
```

- [ ] **Step 6: Commit**

```bash
cd "y:/翻译器项目/ets2-translator"
git add main.py
git commit -m "feat: add provider list UI to settings dialog"
```

---

### Task 4: Integration verification

**Files:**
- Verify: all modules + tests

- [ ] **Step 1: Run all tests**

```bash
cd "y:/翻译器项目/ets2-translator" && python test_logger.py && python test_provider_config.py
```
Expected: Both test suites pass

- [ ] **Step 2: Full import check**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from config import AppConfig, ProviderConfig, load_config, save_config
from translator import Translator, CACHE_SIZE, BATCH_WINDOW
from logger import init_logger, get_logger
from message_types import DisplayMessage, TranslationStats
import main
print('CACHE_SIZE:', CACHE_SIZE)
print('BATCH_WINDOW:', BATCH_WINDOW)
print('All modules OK')
"
```
Expected: Prints constants and "All modules OK"

- [ ] **Step 3: Verify provider migration round-trip**

```bash
cd "y:/翻译器项目/ets2-translator" && python -c "
from config import AppConfig, save_config, load_config
import tempfile, os, json

cfg = AppConfig()
cfg.llm_providers = [
    {'label': 'D1', 'endpoint': 'https://a.com', 'api_key': 'sk-1', 'model': 'm1', 'enabled': True},
    {'label': 'D2', 'endpoint': 'https://b.com', 'api_key': 'sk-2', 'model': 'm2', 'enabled': False},
]

import config as cfg_module
orig_path = cfg_module.CONFIG_PATH
orig_dir = cfg_module.CONFIG_DIR
tmpdir = tempfile.mkdtemp(prefix='ets2_int_')
cfg_module.CONFIG_DIR = tmpdir
cfg_module.CONFIG_PATH = os.path.join(tmpdir, 'config.json')
try:
    save_config(cfg)
    loaded = load_config()
    assert len(loaded.llm_providers) == 2
    assert loaded.llm_providers[0]['label'] == 'D1'
    assert loaded.llm_providers[1]['model'] == 'm2'
    # API keys should be encrypted in file
    with open(cfg_module.CONFIG_PATH) as f:
        raw = f.read()
    assert 'sk-1' not in raw, 'API key not encrypted!'
    assert 'dpapi:' in raw, 'No dpapi prefix found!'
    print('Integration: provider round-trip + encryption OK')
finally:
    cfg_module.CONFIG_PATH = orig_path
    cfg_module.CONFIG_DIR = orig_dir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
print('=== INTEGRATION TESTS PASSED ===')
"
```

- [ ] **Step 4: Commit**

```bash
cd "y:/翻译器项目/ets2-translator" && git add -A && git commit -m "test: integration verification for provider fallback"
```

---

## Execution Order & Dependencies

```
Task 1 (config.py) ──→ Task 2 (translator.py) ──→ Task 4 (integration)
                    └─→ Task 3 (main.py UI)     ──→ Task 4
```

Task 1 must complete first (config changes needed by 2 and 3). Tasks 2 and 3 are independent. Task 4 is last.

**Total estimated commits: 4**
