"""
Translation client — LLM API.
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
from queue import Queue

import httpx

from config import AppConfig
from logger import get_logger
from message_types import DisplayMessage, TranslationStats

_CJK_RE = re.compile(r"[一-鿿]")
_ALPHA_RE = re.compile(r"[a-zA-Z]")

# ── Language detection ──
_LANG_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("日语", re.compile(r"[぀-ゟ゠-ヿ]")),             # Hiragana + Katakana
    ("韩语", re.compile(r"[가-힯ᄀ-ᇿ]")),             # Hangul
    ("俄语", re.compile(r"[Ѐ-ӿ]")),                   # Cyrillic
    ("中文", re.compile(r"[一-鿿]")),                   # CJK
    ("泰语", re.compile(r"[฀-๿]")),                   # Thai
    ("阿拉伯语", re.compile(r"[؀-ۿ]")),               # Arabic
]

_LATIN_MARKERS: list[tuple[str, str]] = [
    ("德语", "ßäöüÄÖÜ"),
    ("法语", "çèéêëàâîïôùûœæÇÈÉÊËÀÂÎÏÔÙÛŒÆ"),
    ("西班牙语", "ñáéíóúü¿¡ÑÁÉÍÓÚÜ"),
    ("葡萄牙语", "ãõâêôàáéíóúçÃÕÂÊÔÀÁÉÍÓÚÇ"),
    ("意大利语", "àèéìòùÀÈÉÌÒÙ"),
]

_ENGLISH_COMMON = frozenset({
    "the", "is", "are", "you", "me", "i", "he", "she", "what",
    "where", "when", "how", "why", "can", "will", "not", "this",
    "that", "and", "for", "have", "with", "your", "but", "all",
    "was", "it", "my", "do", "we", "they", "no", "yes", "just",
})


def detect_language(text: str) -> str:
    """Detect the language of a given text.
    Returns Chinese name of detected language, e.g. '英语', '德语', '俄语'.
    Uses Unicode range detection for non-Latin scripts, and Latin marker
    characters for Latin-based languages.
    """
    if not text or not text.strip():
        return "未知"

    text_stripped = text.strip()

    # Priority 1: Non-Latin scripts (strong signal)
    scores: dict[str, int] = {}
    for lang_name, pattern in _LANG_PATTERNS:
        matches = len(pattern.findall(text_stripped))
        if matches > 0:
            scores[lang_name] = matches

    if scores:
        return max(scores, key=scores.get)

    # Priority 2: Latin-script language detection
    # Use re.ASCII so that \W matches accented Latin chars (ç, é, ñ, etc.)
    if re.match(r"^[a-zA-Z\s\d\W]+$", text_stripped[:20], re.ASCII):
        best_lang = ""
        best_score = 0
        for lang_name, markers in _LATIN_MARKERS:
            score = sum(1 for ch in markers if ch in text_stripped)
            if score > best_score:
                best_score = score
                best_lang = lang_name

        if best_lang and best_score > 0:
            return best_lang

        words = set(text_stripped.lower().split())
        if words & _ENGLISH_COMMON:
            return "英语"

        return "英语"

    return "未知"


# ── Target-language script patterns for mixed-text splitting ──
# Maps config target_language codes to regex patterns matching that script.
_TARGET_SCRIPT_PATTERNS: dict[str, re.Pattern] = {
    "zh-CN": re.compile(r"[一-鿿　-〿＀-￯]"),  # CJK + Chinese punct
    "zh-TW": re.compile(r"[一-鿿　-〿＀-￯]"),
    "ja": re.compile(r"[぀-ゟ゠-ヿ一-鿿]"),     # Hiragana + Katakana + Kanji
    "ko": re.compile(r"[가-힯ᄀ-ᇿ㄰-㆏]"),     # Hangul
    "ru": re.compile(r"[Ѐ-ӿ]"),                                # Cyrillic
    "th": re.compile(r"[฀-๿]"),                                # Thai
    "ar": re.compile(r"[؀-ۿݐ-ݿ]"),                   # Arabic
}
# For script-based languages not in the map, fallback to treating Latin-script
# (ASCII + Latin-extended) as "foreign" and everything else as "target".
_LATIN_SCRIPT_RE = re.compile(r"[a-zA-ZÀ-ɏḀ-ỿ]")


def _get_target_script_pattern(target_lang: str) -> re.Pattern | None:
    """Return the regex matching the script of target_lang, or None."""
    lang = target_lang.split("-")[0].lower()
    return _TARGET_SCRIPT_PATTERNS.get(target_lang) or _TARGET_SCRIPT_PATTERNS.get(lang)


def split_mixed_text(text: str, target_lang: str) -> list[tuple[str, bool]]:
    """Split text into (segment, is_target_lang) pairs.

    Walks the text character by character, grouping contiguous characters
    that are either in the target language script or not. Punctuation/whitespace
    is absorbed into the preceding segment.

    Returns [] for empty/whitespace-only text.
    """
    if not text or not text.strip():
        return []

    target_re = _get_target_script_pattern(target_lang)
    if target_re is None:
        # No specific script pattern — treat all text as foreign
        return [(text, False)]

    result: list[tuple[str, bool]] = []
    current_chars: list[str] = []
    current_is_target: bool | None = None

    for ch in text:
        is_target = bool(target_re.match(ch))

        if current_is_target is None:
            current_is_target = is_target
            current_chars.append(ch)
        elif is_target == current_is_target:
            current_chars.append(ch)
        else:
            # Script boundary — flush current segment preserving internal whitespace
            segment = "".join(current_chars)
            if segment.strip():
                result.append((segment, current_is_target))
            current_chars = [ch]
            current_is_target = is_target

    # Flush last segment
    if current_chars:
        segment = "".join(current_chars)
        if segment.strip():
            result.append((segment, current_is_target))

    # Strip leading whitespace from first segment and trailing from last segment
    if result:
        first_seg, first_flag = result[0]
        result[0] = (first_seg.lstrip(), first_flag)
        last_seg, last_flag = result[-1]
        result[-1] = (last_seg.rstrip(), last_flag)

    return result


def reassemble_mixed(
    segments: list[tuple[str, bool]],
    translations: dict[str, str],
) -> str:
    """Reassemble mixed-language segments after translating foreign parts.

    Target-language segments are kept as-is. Foreign segments are replaced
    with their translations (falling back to original if not translated).
    """
    parts: list[str] = []
    for text, is_target in segments:
        if is_target:
            parts.append(text)
        else:
            parts.append(translations.get(text, text))
    return "".join(parts)


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
        self._rr_index = 0                # round-robin dispatch index
        self._last_provider = "?"         # last used provider label (for logging)
        self._last_model = "?"            # last used model name (for logging)

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
                    timestamp=msg.timestamp,
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
                    timestamp=msg.timestamp,
                    is_system=msg.is_system,
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

        self._flush_llm(batch)

    def _translate_with_mixed_lang(self, text: str, target_lang: str) -> str:
        """Translate text, preserving segments already in the target language.

        If the text contains mixed scripts (target language + foreign), it is
        split into segments. Target-language segments are kept as-is; only
        foreign segments are sent to the LLM API. Pure foreign or pure target
        texts are handled normally (pure target is returned unchanged).
        """
        if not text or not text.strip():
            return text

        segments = split_mixed_text(text, target_lang)
        if not segments:
            return text

        # Count foreign segments
        foreign_segments = [(i, s) for i, (s, is_target) in enumerate(segments) if not is_target]
        target_segments = [s for s, is_target in segments if is_target]

        if not foreign_segments:
            # All text is already in the target language — nothing to translate
            return text

        if not target_segments:
            # Pure foreign — translate normally
            return self._call_api(text)

        # Mixed: translate each foreign segment individually
        translations: dict[str, str] = {}
        for _, fseg in foreign_segments:
            stripped = fseg.strip()
            if stripped:
                try:
                    translations[fseg] = self._call_api(stripped)
                except Exception:
                    translations[fseg] = fseg  # fallback to original
            else:
                translations[fseg] = fseg

        return reassemble_mixed(segments, translations)

    def _flush_llm(self, batch):
        try:
            if len(batch) == 1:
                text = batch[0].text
                target_lang = self.cfg.target_language
                translated = self._translate_with_mixed_lang(text, target_lang)
                self._cache.put(text, translated)
                detected = detect_language(text)
                self.out_queue.put(DisplayMessage(
                    player_name=batch[0].player_name,
                    original_text=text,
                    translated_text=translated,
                    detected_language=detected,
                    timestamp=batch[0].timestamp,
                    is_system=batch[0].is_system,
                ))
                log = get_logger()
                if log and hasattr(self, '_last_provider'):
                    log.translation_log(
                        getattr(self, '_last_provider', '?'),
                        getattr(self, '_last_model', '?'),
                        text,
                        translated
                    )
            else:
                combined = BATCH_SEPARATOR.join(m.text for m in batch)
                result = self._call_api(combined)
                parts = [p.strip() for p in result.split(BATCH_SEPARATOR)]
                for i, msg in enumerate(batch):
                    if i < len(parts):
                        trans = parts[i]
                        self._cache.put(msg.text, trans)  # only cache real translations
                    else:
                        trans = msg.text  # fallback — do NOT cache, let retry happen
                    detected = detect_language(msg.text)
                    self.out_queue.put(DisplayMessage(
                        player_name=msg.player_name,
                        original_text=msg.text,
                        translated_text=trans,
                        detected_language=detected,
                        timestamp=msg.timestamp,
                        is_system=msg.is_system,
                    ))
                    log = get_logger()
                    if log and hasattr(self, '_last_provider'):
                        log.translation_log(
                            getattr(self, '_last_provider', '?'),
                            getattr(self, '_last_model', '?'),
                            msg.text,
                            trans
                        )
        except Exception as e:
            err_msg = self._format_error(e)
            log = get_logger()
            if log:
                log.error("LLM", f"翻译失败: {err_msg}")
            for msg in batch:
                detected = detect_language(msg.text)
                self.out_queue.put(DisplayMessage(
                    player_name=msg.player_name,
                    original_text=msg.text,
                    translated_text=err_msg,
                    detected_language=detected,
                    timestamp=msg.timestamp,
                    is_system=msg.is_system,
                ))

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

    def _call_provider(self, provider: dict, text: str, timeout: float = 8.0) -> str:
        """Call a single LLM provider. Raises exception on failure.
        Supports extra_headers, extra_body, per-provider timeout, and api_format.
        """
        endpoint = provider.get("endpoint", "").strip()
        if not endpoint:
            raise Exception("Provider endpoint is empty")
        if not endpoint.startswith(("http://", "https://")):
            endpoint = "https://" + endpoint

        api_key = provider.get("api_key", "")
        model = provider.get("model", "")
        api_format = provider.get("api_format", "openai")

        # Per-provider timeout overrides the caller's timeout
        provider_timeout = timeout
        if "timeout" in provider and isinstance(provider["timeout"], (int, float)):
            provider_timeout = float(provider["timeout"])

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": f'把以下文字翻译成简体中文，只输出译文：{text}'},
            ],
            "temperature": 0.2,
            "max_tokens": 500 if BATCH_SEPARATOR not in text else 500 * text.count(BATCH_SEPARATOR) + 500,
        }

        # Merge extra_body fields (user-specified overrides, e.g. temperature)
        extra_body = provider.get("extra_body", {})
        if isinstance(extra_body, dict) and extra_body:
            payload.update(extra_body)

        headers = {
            "Content-Type": "application/json",
        }

        # Build auth header based on api_format
        if api_format == "anthropic":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

        # Merge extra_headers (template vars like {api_key} are resolved)
        extra_headers = provider.get("extra_headers", {})
        if isinstance(extra_headers, dict) and extra_headers:
            for k, v in extra_headers.items():
                resolved = v.replace("{api_key}", api_key)
                headers[k] = resolved

        client = httpx.Client(timeout=provider_timeout)
        try:
            resp = client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        finally:
            client.close()

    def _call_api(self, text: str) -> str:
        """Round-robin provider dispatch with in-flight request merging.
        Merges in-flight identical requests. Filters cooling providers."""
        if self._should_skip(text):
            return text

        # Request merging: wait for identical in-flight request
        existing = None
        with self._in_flight_lock:
            existing = self._in_flight.get(text)
            if existing is None:
                self._in_flight[text] = threading.Event()
            else:
                event_to_await = existing

        if existing is not None:
            event_to_await.wait(timeout=10.0)
            with self._in_flight_lock:
                result = self._in_flight_results.get(text)
            if result is not None:
                return result
            # Timeout or no result — fall through to translate

        try:
            result, provider_label, model = self._call_api_internal(text)
            self._last_provider = provider_label
            self._last_model = model
            with self._in_flight_lock:
                self._in_flight_results[text] = result
            return result
        finally:
            with self._in_flight_lock:
                event = self._in_flight.pop(text, None)
                if event:
                    event.set()  # wake waiters first — they read _in_flight_results

    def _call_api_internal(self, text: str) -> tuple[str, str, str]:
        """Round-robin provider selection with circuit breaker fallback.
        Returns (translated_text, provider_label, model_name)."""
        providers = [p for p in self.cfg.llm_providers if p.get("enabled", True)]
        if not providers:
            return self._call_api_legacy(text), "legacy", ""

        # Filter out cooling providers
        active = [p for p in providers if not self._is_cooling(p.get("label", "unknown"))]
        if not active:
            log = get_logger()
            if log:
                log.warn("LLM", "所有 Provider 均处于冷却期，强制重试全部")
            active = providers

        # Round-robin selection
        with self._health_lock:
            idx = getattr(self, '_rr_index', 0)
            setattr(self, '_rr_index', (idx + 1) % len(active))

        log = get_logger()
        selected = active[idx]
        label = selected.get("label", "unknown")
        model = selected.get("model", "")

        # Try selected provider
        try:
            result = self._call_provider(selected, text)
            self._note_provider_result(label, True)
            if log:
                log.info("LLM", f"轮转成功 [{idx}/{len(active)}]: {label}")
            return result, label, model
        except Exception as e:
            err = self._format_error(e)
            self._note_provider_result(label, False)
            if log:
                log.warn("LLM", f"轮转失败: {label} - {err}")

        # Fallback: try remaining providers in round-robin order
        for offset in range(1, len(active)):
            candidate = active[(idx + offset) % len(active)]
            clabel = candidate.get("label", "unknown")
            cmodel = candidate.get("model", "")
            try:
                result = self._call_provider(candidate, text)
                self._note_provider_result(clabel, True)
                if log:
                    log.info("LLM", f"回退成功 [{offset}]: {clabel}")
                return result, clabel, cmodel
            except Exception as e:
                err = self._format_error(e)
                self._note_provider_result(clabel, False)
                if log:
                    log.warn("LLM", f"回退失败: {clabel} - {err}")

        # Last resort: retry all including cooling
        for p in providers:
            plabel = p.get("label", "unknown")
            pmodel = p.get("model", "")
            try:
                result = self._call_provider(p, text, timeout=8.0)
                self._note_provider_result(plabel, True)
                return result, plabel, pmodel
            except Exception:
                self._note_provider_result(plabel, False)
                time.sleep(0.18)

        raise Exception("所有 Provider 翻译失败")

    def _call_api_legacy(self, text: str) -> str:
        """Legacy single-API fallback (used when llm_providers is empty)."""
        if self._should_skip(text):
            return text

        payload = {
            "model": self.cfg.api_model,
            "messages": [
                {"role": "user", "content": f'把以下文字翻译成简体中文，只输出译文：{text}'},
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
        """Skip messages already in the target language (all supported languages)."""
        return _should_skip_internal(text, self.cfg.target_language)

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


# Language names in Chinese for the send instruction template
_SEND_LANG_NAMES: dict[str, str] = {
    "en": "英语", "ja": "日语", "ko": "韩语",
    "de": "德语", "fr": "法语", "es": "西班牙语",
    "ru": "俄语", "pt": "葡萄牙语", "it": "意大利语",
}


def _should_skip_internal(text: str, target_lang: str) -> bool:
    """Skip translation if text appears to already be in the target language."""
    if not text or not text.strip():
        return True
    detected = detect_language(text)
    _name_to_code = {
        "中文": "zh", "英语": "en", "日语": "ja", "韩语": "ko",
        "俄语": "ru", "德语": "de", "法语": "fr",
        "西班牙语": "es", "葡萄牙语": "pt", "意大利语": "it",
        "泰语": "th", "阿拉伯语": "ar",
    }
    code = _name_to_code.get(detected, "")
    if code and target_lang.startswith(code):
        return True
    return False


def _call_single_provider(p: dict, text: str, target_lang: str, cfg: AppConfig) -> str:
    """Call a single LLM provider for send translation."""
    lang_name = _SEND_LANG_NAMES.get(target_lang, "英语")
    user_msg = f'帮我把"{text}"翻译成{lang_name}'
    ep = p["endpoint"].strip()
    if not ep.startswith(("http://", "https://")):
        ep = "https://" + ep
    payload = {
        "model": p["model"],
        "messages": [
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }
    # Merge extra_body fields
    extra_body = p.get("extra_body", {})
    if isinstance(extra_body, dict) and extra_body:
        payload.update(extra_body)

    api_key = p.get("api_key", "")
    api_format = p.get("api_format", "openai")
    headers = {
        "Content-Type": "application/json",
    }
    if api_format == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    # Merge extra_headers
    extra_headers = p.get("extra_headers", {})
    if isinstance(extra_headers, dict) and extra_headers:
        for k, v in extra_headers.items():
            resolved = v.replace("{api_key}", api_key)
            headers[k] = resolved

    resp = httpx.post(ep, json=payload, headers=headers, timeout=8.0)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _legacy_send_translate(cfg: AppConfig, text: str, target_lang: str) -> str:
    """Legacy single-API fallback for send translation (no providers configured)."""
    lang_name = _SEND_LANG_NAMES.get(target_lang, "英语")
    user_msg = f'帮我把"{text}"翻译成{lang_name}'
    endpoint = cfg.api_endpoint.strip()
    if not endpoint.startswith(("http://", "https://")):
        endpoint = "https://" + endpoint
    payload = {
        "model": cfg.api_model,
        "messages": [
            {"role": "user", "content": user_msg},
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
    return data["choices"][0]["message"]["content"].strip()


def translate_for_send(cfg: AppConfig, text: str) -> str:
    """Translate player's message to target language for sending."""
    target_lang = cfg.send_target_language
    if not text or not text.strip():
        return text

    if _should_skip_internal(text, target_lang):
        return text

    providers = [p for p in cfg.llm_providers if p.get("enabled", True)]
    if not providers:
        return _legacy_send_translate(cfg, text, target_lang)

    # Try each provider in order
    for p in providers:
        api_format = p.get("api_format", "openai")
        try:
            return _call_single_provider(p, text, target_lang, cfg)
        except Exception:
            continue

    raise Exception("所有 Provider 发送翻译失败")


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
