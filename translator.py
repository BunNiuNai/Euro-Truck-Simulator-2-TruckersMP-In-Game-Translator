"""
Translation clients - LLM API + Baidu Translate API.
Batch mode (LLM only): collects messages within a short window, sends them as one request.
LRU cache: avoids re-translating identical strings.
"""
import hashlib
import json
import random
import re
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

import httpx

from config import AppConfig, get_send_prompt
from logger import get_logger
from message_types import DisplayMessage, TranslationStats

_CJK_RE = re.compile(r"[一-鿿]")
_ALPHA_RE = re.compile(r"[a-zA-Z]")

CACHE_SIZE = 1000
BATCH_WINDOW = 0.3  # seconds to wait for more messages before sending batch
BATCH_SEPARATOR = "\n---\n"


class ProviderHealth:
    """Tracks health state for one provider (circuit breaker pattern)."""
    __slots__ = ("failures", "cool_until")

    def __init__(self):
        self.failures: int = 0
        self.cool_until: float = 0.0


class LRUCache:
    def __init__(self, maxsize: int = CACHE_SIZE):
        self.maxsize = maxsize
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: str, value: str):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)


class Translator(threading.Thread):
    """Background worker: batches messages, translates via LLM API, caches results."""

    def __init__(self, cfg: AppConfig, in_queue: Queue, out_queue: Queue):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.in_queue = in_queue
        self.out_queue = out_queue
        self._stop_event = threading.Event()
        self._cache = LRUCache(CACHE_SIZE)
        self._local = threading.local()  # per-thread httpx client (httpx.Client is NOT thread-safe)
        self.stats = TranslationStats()
        self._msg_since_log = 0  # counter for periodic stats logging
        self._provider_health: dict[str, ProviderHealth] = {}
        self._health_lock = threading.Lock()
        self._in_flight: dict[str, threading.Event] = {}
        self._in_flight_results: dict[str, str] = {}
        self._in_flight_lock = threading.Lock()

    def _get_client(self) -> httpx.Client:
        """Get or create a per-thread httpx client."""
        client = getattr(self._local, 'client', None)
        if client is None:
            self._local.client = httpx.Client(timeout=8.0)
            return self._local.client
        return client

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
                        self._local.client = None
                        log = get_logger()
                        if log:
                            log.info("SYS", "配置已热重载")
                except OSError:
                    pass
                # Periodic cleanup: clear stale in-flight results (>300 entries)
                with self._in_flight_lock:
                    if len(self._in_flight_results) > 300:
                        self._in_flight_results.clear()

            try:
                timeout = 0.3
                if batch and batch_deadline:
                    remaining = batch_deadline - time.monotonic()
                    timeout = max(0, min(0.3, remaining))
                msg = self.in_queue.get(timeout=timeout)
            except Exception:
                # Timeout — flush batch if deadline passed
                if batch and time.monotonic() >= batch_deadline:
                    self._flush(batch)
                    batch = []
                    batch_deadline = None
                continue

            if msg is None:
                if batch:
                    self._flush(batch)
                break

            # Skip own messages (already Chinese)
            if msg.is_self:
                self.stats.self_skipped += 1
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=msg.text,
                    is_self=True,
                ))
                continue

            # Check cache
            cached = self._cache.get(msg.text)
            if cached is not None:
                self.stats.cached += 1
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=cached,
                    is_self=msg.is_self,
                ))
                continue

            # Add to batch
            batch.append(msg)
            if batch_deadline is None:
                batch_deadline = time.monotonic() + BATCH_WINDOW

            # Flush if batch is large enough
            if len(batch) >= 8:
                self._flush(batch)
                batch = []
                batch_deadline = None

    def _flush(self, batch):
        if not batch:
            return
        self.stats.translated += len(batch)
        self._msg_since_log += len(batch)

        # Log stats every 50 messages
        if self._msg_since_log >= 50:
            self._msg_since_log = 0
            log = get_logger()
            if log:
                log.info("LLM", f"翻译统计: 翻译={self.stats.translated} 缓存={self.stats.cached} "
                        f"跳过={self.stats.self_skipped} 节省={self.stats.savings_pct()}")

        if self.cfg.translation_backend == "baidu":
            self._flush_baidu(batch)
        elif self.cfg.translation_backend == "llm+baidu":
            self._flush_hybrid(batch)
        else:
            self._flush_llm(batch)

    def _flush_llm(self, batch):
        try:
            if len(batch) == 1:
                text = batch[0].text
                translated = self._call_api(text)
                self._cache.put(text, translated)
                self.out_queue.put(DisplayMessage(
                    player_name=batch[0].player_name,
                    original_text=text,
                    translated_text=translated,
                ))
            else:
                combined = BATCH_SEPARATOR.join(m.text for m in batch)
                result = self._call_api(combined)
                parts = [p.strip() for p in result.split(BATCH_SEPARATOR)]
                for i, msg in enumerate(batch):
                    trans = parts[i] if i < len(parts) else msg.text
                    self._cache.put(msg.text, trans)
                    self.out_queue.put(DisplayMessage(
                        player_name=msg.player_name,
                        original_text=msg.text,
                        translated_text=trans,
                    ))
        except Exception as e:
            err_msg = self._format_error(e)
            log = get_logger()
            if log:
                log.error("LLM", f"翻译失败: {err_msg}")
            for msg in batch:
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=err_msg,
                ))

    def _flush_baidu(self, batch):
        for msg in batch:
            try:
                translated = translate_via_baidu(
                    self.cfg.baidu_appid, self.cfg.baidu_secret, msg.text
                )
                self._cache.put(msg.text, translated)
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=translated,
                ))
            except Exception as e:
                log = get_logger()
                if log:
                    log.error("BDU", f"百度翻译失败: {e}")
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=f"[百度翻译失败] {e}",
                ))

    def _flush_hybrid(self, batch):
        """LLM translates first, Baidu verifies in parallel and overrides if different."""
        # Step 1: get LLM translations (reuse batch logic)
        llm_results: dict[str, str] = {}  # text -> translation
        try:
            if len(batch) == 1:
                text = batch[0].text
                llm_results[text] = self._call_api(text)
            else:
                combined = BATCH_SEPARATOR.join(m.text for m in batch)
                result = self._call_api(combined)
                parts = [p.strip() for p in result.split(BATCH_SEPARATOR)]
                for i, msg in enumerate(batch):
                    llm_results[msg.text] = parts[i] if i < len(parts) else msg.text
        except Exception as e:
            err_msg = self._format_error(e)
            for msg in batch:
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=err_msg,
                ))
            return

        # Step 2: get Baidu translations in parallel
        baidu_results: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    translate_via_baidu,
                    self.cfg.baidu_appid, self.cfg.baidu_secret, msg.text,
                ): msg.text
                for msg in batch
            }
            for future in as_completed(futures):
                text = futures[future]
                try:
                    baidu_results[text] = future.result()
                except Exception:
                    pass  # Baidu failed for this text, will fall back to LLM

        # Step 3: compare and emit
        baidu_override_count = 0
        for msg in batch:
            llm_trans = llm_results.get(msg.text, msg.text)
            baidu_trans = baidu_results.get(msg.text)
            if baidu_trans is not None and _translations_differ(llm_trans, baidu_trans):
                baidu_override_count += 1
                # Baidu overrides LLM
                self._cache.put(msg.text, baidu_trans)
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=baidu_trans,
                    baidu_fixed=True,
                ))
            else:
                self._cache.put(msg.text, llm_trans)
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=llm_trans,
                ))

        if baidu_override_count > 0:
            log = get_logger()
            if log:
                log.info("BDU", f"百度纠错: {baidu_override_count}/{len(batch)} 条被覆盖")

    # ── Circuit breaker ──

    def _is_cooling(self, label: str) -> bool:
        """Check if a provider is in cooldown (circuit breaker open)."""
        with self._health_lock:
            health = self._provider_health.get(label)
            if health and health.cool_until > 0:
                if time.monotonic() < health.cool_until:
                    return True
        return False

    def _note_provider_result(self, label: str, success: bool) -> None:
        """Update provider health after a translation attempt (thread-safe)."""
        with self._health_lock:
            if label not in self._provider_health:
                self._provider_health[label] = ProviderHealth()
            h = self._provider_health[label]
            log = get_logger()

            if success:
                if h.failures > 0:
                    if log:
                        log.info("LLM", f"Provider {label} 已恢复（之前 {h.failures} 次失败）")
                h.failures = 0
                h.cool_until = 0
            else:
                h.failures += 1
                if h.failures >= 3:
                    duration = min(30 * (2 ** (h.failures - 3)), 120)
                    h.cool_until = time.monotonic() + duration
                    if log:
                        log.warn("LLM", f"Provider {label} 进入冷却 {duration}s（连续 {h.failures} 次失败）")

    # ── Provider calling ──

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

        resp = self._get_client().post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _call_api(self, text: str) -> str:
        """Call providers with parallel race + serial fallback.
        Merges in-flight identical requests. Filters cooling providers."""
        if self._should_skip(text):
            return text

        # Request merging: wait for identical in-flight request
        with self._in_flight_lock:
            existing = self._in_flight.get(text)
            if existing is None:
                self._in_flight[text] = threading.Event()
            else:
                # Release lock before waiting so producer can signal
                event_to_await = existing

        if existing is not None:
            event_to_await.wait(timeout=10.0)
            with self._in_flight_lock:
                result = self._in_flight_results.get(text)
            if result is not None:
                return result
            # Timeout or no result — fall through to translate

        try:
            result = self._call_api_internal(text)
            with self._in_flight_lock:
                self._in_flight_results[text] = result
            return result
        finally:
            with self._in_flight_lock:
                event = self._in_flight.pop(text, None)
                if event:
                    event.set()  # wake waiters first — they read _in_flight_results
                # Keep result briefly so late waiters can still read it
                # (LRU cache handles dedup; old entries are harmless)

    def _call_api_internal(self, text: str) -> str:
        """Provider parallel race + serial fallback with circuit breaker."""
        providers = [p for p in self.cfg.llm_providers if p.get("enabled", True)]
        if not providers:
            return self._call_api_legacy(text)

        # Filter out cooling providers
        active = [p for p in providers if not self._is_cooling(p["label"])]
        if not active:
            log = get_logger()
            if log:
                log.warn("LLM", "所有 Provider 均处于冷却期，强制重试全部")
            active = providers

        skipped = len(providers) - len(active)
        if skipped > 0:
            log = get_logger()
            if log:
                cooling_names = [p["label"] for p in providers if p not in active]
                log.warn("LLM", f"跳过冷却中的 Provider: {', '.join(cooling_names)}")

        log = get_logger()

        # Round 1: Parallel race (only active providers)
        errors = []
        with ThreadPoolExecutor(max_workers=min(len(active), 4)) as executor:
            futures = {
                executor.submit(self._call_provider, p, text): p["label"]
                for p in active
            }
            for future in as_completed(futures):
                label = futures[future]
                try:
                    result = future.result()
                    self._note_provider_result(label, True)
                    if log:
                        log.info("LLM", f"竞速成功: {label}")
                    return result
                except Exception as e:
                    err = self._format_error(e)
                    errors.append(f"{label}: {err}")
                    self._note_provider_result(label, False)
                    if log:
                        log.warn("LLM", f"竞速失败: {label} - {err}")

        # Round 2: Serial retry (active + cooling, 180ms apart)
        if log:
            log.warn("LLM", f"第一轮全部失败，进入串行重试 ({len(active)} providers)")
        retry_list = active + [p for p in providers if p not in active]
        for p in retry_list:
            try:
                result = self._call_provider(p, text)
                self._note_provider_result(p["label"], True)
                if log:
                    log.info("LLM", f"重试成功: {p['label']}")
                return result
            except Exception:
                self._note_provider_result(p["label"], False)
                time.sleep(0.18)

        raise Exception(" | ".join(errors) if errors else "所有 Provider 翻译失败")

    def _call_api_legacy(self, text: str) -> str:
        """Legacy single-API fallback (used when llm_providers is empty)."""
        if self._should_skip(text):
            return text

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

        resp = self._get_client().post(self.cfg.api_endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _should_skip(self, text: str) -> bool:
        # Skip messages already in the target language
        if self.cfg.target_language.startswith("zh"):
            cjk = len(_CJK_RE.findall(text))
            alpha = len(_ALPHA_RE.findall(text))
            if cjk > alpha and cjk > len(text) * 0.3:
                return True
        return False

    def _format_error(self, exc: Exception) -> str:
        if isinstance(exc, httpx.ConnectError):
            return "[网络错误] 无法连接到 API 服务器，请检查地址和网络"
        if isinstance(exc, httpx.TimeoutException):
            return "[请求超时] API 服务器响应超时，请稍后重试"
        if isinstance(exc, httpx.HTTPStatusError):
            code = exc.response.status_code
            if code == 401:
                return "[认证失败] API 密钥无效，请检查设置"
            if code == 403:
                return "[权限不足] 无权访问该 API，请检查密钥权限"
            if code == 429:
                return "[请求过于频繁] 请稍后重试"
            if code in (500, 502, 503):
                return f"[服务器错误 {code}] API 服务器异常，请稍后重试"
            return f"[HTTP 错误 {code}] {exc.response.reason_phrase}"
        if isinstance(exc, (KeyError, IndexError)):
            return "[响应格式错误] API 返回了意外的数据结构"
        if isinstance(exc, json.JSONDecodeError):
            return "[响应格式错误] API 返回了无效的 JSON"
        return f"[翻译失败] {exc}"

    def stop(self):
        self._stop_event.set()
        # Close per-thread client if one was created
        client = getattr(self._local, 'client', None)
        if client is not None:
            client.close()


def test_connection(endpoint: str, api_key: str, model: str) -> tuple:
    """Test API connectivity with a minimal request. Returns (success: bool, message: str)."""
    endpoint = endpoint.strip()
    if endpoint and not endpoint.startswith(("http://", "https://")):
        endpoint = "https://" + endpoint

    try:
        client = httpx.Client(timeout=8.0)
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Hi"},
            ],
            "max_tokens": 5,
            "temperature": 0,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        resp = client.post(endpoint, json=payload, headers=headers)
        client.close()
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        log = get_logger()
        if log:
            log.info("LLM", f"连通测试 OK | {model} @ {endpoint}")
        return True, f"连通成功 — {content[:60]}"
    except httpx.ConnectError:
        log = get_logger()
        if log:
            log.error("LLM", "连通测试失败: 无法连接到 API 服务器")
        return False, "无法连接到 API 服务器，请检查地址和网络"
    except httpx.TimeoutException:
        return False, "连接超时，请检查网络或 API 地址是否可访问"
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        detail = _parse_api_error(e.response)
        if code == 401:
            return False, f"API Key 无效 (401){detail}"
        if code == 403:
            return False, f"无权访问 (403){detail}"
        if code == 404:
            return False, f"未找到 (404){detail}\n请检查 API 地址路径和模型名称"
        if code == 429:
            return False, "请求过于频繁 (429)，请稍后重试"
        return False, f"HTTP 错误 {code}{detail}"
    except (KeyError, IndexError):
        return False, "API 响应格式异常，请确认 API 地址指向 chat/completions 端点"
    except json.JSONDecodeError:
        return False, "API 返回了无效的 JSON，请确认 API 地址正确"
    except Exception as e:
        return False, f"连接失败: {e}"


SEND_SYSTEM_PROMPT = get_send_prompt()


def translate_to_english(cfg: AppConfig, text: str) -> str:
    """Translate Chinese text to English for sending in chat.
    Returns the translated text, or raises an exception on error."""
    if cfg.translation_backend == "baidu":
        return translate_to_english_via_baidu(cfg.baidu_appid, cfg.baidu_secret, text)

    # Use multi-provider if available
    providers = [p for p in cfg.llm_providers if p.get("enabled", True)]
    if providers:
        errors = []
        with ThreadPoolExecutor(max_workers=min(len(providers), 4)) as executor:
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
                    llm_result = future.result()
                    # Hybrid: Baidu verify
                    if cfg.translation_backend == "llm+baidu" and cfg.baidu_appid and cfg.baidu_secret:
                        try:
                            baidu_result = translate_to_english_via_baidu(cfg.baidu_appid, cfg.baidu_secret, text)
                            if _translations_differ(llm_result, baidu_result):
                                return baidu_result
                        except Exception:
                            pass
                    return llm_result
                except Exception as e:
                    errors.append(str(e))
        raise Exception(" | ".join(errors) if errors else "所有 Provider 翻译失败")

    # Legacy single-API fallback
    endpoint = cfg.api_endpoint.strip()
    if not endpoint.startswith(("http://", "https://")):
        endpoint = "https://" + endpoint

    payload = {
        "model": cfg.api_model,
        "messages": [
            {"role": "system", "content": SEND_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.api_key}",
    }
    resp = httpx.post(endpoint, json=payload, headers=headers, timeout=8.0)
    resp.raise_for_status()
    data = resp.json()
    llm_result = data["choices"][0]["message"]["content"].strip()

    # Hybrid mode: Baidu verifies and overrides if different
    if cfg.translation_backend == "llm+baidu" and cfg.baidu_appid and cfg.baidu_secret:
        try:
            baidu_result = translate_to_english_via_baidu(cfg.baidu_appid, cfg.baidu_secret, text)
            if _translations_differ(llm_result, baidu_result):
                return baidu_result
        except Exception:
            pass

    return llm_result


def translate_via_baidu(appid: str, secret: str, text: str, to_lang: str = "zh") -> str:
    """Translate text using Baidu Translate API.
    https://fanyi-api.baidu.com/api/trans/vip/translate
    """
    endpoint = "https://fanyi-api.baidu.com/api/trans/vip/translate"
    salt = str(random.randint(10000, 99999))
    sign_str = appid + text + salt + secret
    sign = hashlib.md5(sign_str.encode()).hexdigest()

    params = {
        "q": text,
        "from": "auto",
        "to": to_lang,
        "appid": appid,
        "salt": salt,
        "sign": sign,
    }
    resp = httpx.get(endpoint, params=params, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if "error_code" in data:
        err_msg = data.get("error_msg", data["error_code"])
        raise Exception(f"百度翻译错误 {data['error_code']}: {err_msg}")
    return data["trans_result"][0]["dst"]


def translate_to_english_via_baidu(appid: str, secret: str, text: str) -> str:
    """Translate Chinese text to English via Baidu API."""
    return translate_via_baidu(appid, secret, text, to_lang="en")


def _translations_differ(a: str, b: str) -> bool:
    """Check if two translations are meaningfully different (not just punctuation)."""
    a_norm = a.strip().lower().rstrip(".!?;:。！？；：…\"'\"")
    b_norm = b.strip().lower().rstrip(".!?;:。！？；：…\"'\"")
    return a_norm != b_norm


def test_baidu_connection(appid: str, secret: str) -> tuple:
    """Test Baidu API connectivity with a minimal request. Returns (success, message)."""
    if not appid or not secret:
        return False, "请填写百度翻译 APP ID 和密钥"
    try:
        result = translate_via_baidu(appid, secret, "Hello")
        log = get_logger()
        if log:
            log.info("BDU", "连通测试 OK | 百度翻译 API 标准版")
        return True, f"连通成功 — {result[:60]}"
    except Exception as e:
        log = get_logger()
        if log:
            log.error("BDU", f"连通测试失败: {e}")
        return False, f"连通失败: {e}"


def _parse_api_error(response) -> str:
    try:
        body = response.json()
        err = body.get("error", {})
        msg = err.get("message", "") if isinstance(err, dict) else str(err)
        if msg:
            return f" — {msg}"
    except Exception:
        pass
    return ""
