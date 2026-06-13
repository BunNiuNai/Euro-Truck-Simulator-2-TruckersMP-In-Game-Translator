"""
Configuration management for ETS2 Chat Translator.
Reads/writes JSON config in Documents/ETS2 Translator/config.json
Documents path is obtained from Windows registry (same method as the reference DLL).
"""
import base64
import ctypes
import json
import os
import tempfile
import winreg
from ctypes import wintypes
from dataclasses import dataclass, asdict, field

VERSION = "v1.2.1"

# ── Windows DPAPI for encrypting sensitive config fields ──


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.c_void_p),
    ]


_crypt32 = ctypes.windll.crypt32
_crypt32.CryptProtectData.argtypes = [
    ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(_DATA_BLOB),
]
_crypt32.CryptProtectData.restype = wintypes.BOOL
_crypt32.CryptUnprotectData.argtypes = [
    ctypes.POINTER(_DATA_BLOB), wintypes.LPCWSTR,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(_DATA_BLOB),
]
_crypt32.CryptUnprotectData.restype = wintypes.BOOL

_kernel32 = ctypes.windll.kernel32
_kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
_kernel32.LocalFree.restype = wintypes.HLOCAL


def _dpapi_encrypt(plaintext: str) -> str:
    """Encrypt a string using Windows DPAPI. Returns base64-encoded ciphertext."""
    data = plaintext.encode("utf-8")
    buf = ctypes.create_string_buffer(data)
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.c_void_p))
    blob_out = _DATA_BLOB()
    if not _crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptProtectData failed")
    try:
        encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        _kernel32.LocalFree(blob_out.pbData)


def _dpapi_decrypt(ciphertext: str) -> str:
    """Decrypt a base64-encoded DPAPI ciphertext. Returns plaintext."""
    encrypted = base64.b64decode(ciphertext.encode("ascii"))
    buf = ctypes.create_string_buffer(encrypted)
    blob_in = _DATA_BLOB(len(encrypted), ctypes.cast(buf, ctypes.c_void_p))
    blob_out = _DATA_BLOB()
    if not _crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0,
        ctypes.byref(blob_out),
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    finally:
        _kernel32.LocalFree(blob_out.pbData)


# Fields that should be encrypted at rest
_SECRET_FIELDS = {"api_key", "baidu_secret"}
# Prefix to identify encrypted values in JSON
_ENC_PREFIX = "dpapi:"


def _is_encrypted(value: str) -> bool:
    return value.startswith(_ENC_PREFIX)


def _maybe_encrypt(field: str, value: str) -> str:
    """Encrypt value if field is sensitive and value is not already encrypted."""
    if not value:
        return value
    if _is_encrypted(value):
        return value
    if field in _SECRET_FIELDS:
        return _ENC_PREFIX + _dpapi_encrypt(value)
    return value


def _maybe_decrypt(field: str, value: str) -> str:
    """Decrypt value if it is encrypted."""
    if not value:
        return value
    if _is_encrypted(value):
        try:
            return _dpapi_decrypt(value[len(_ENC_PREFIX):])
        except Exception:
            return value
    return value


def get_documents_path():
    """Get the user's Documents folder from Windows registry.

    Same approach as the reference DLL: reads the 'Personal' value from
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders.
    Falls back to USERPROFILE\\Documents if registry lookup fails.
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        path, _ = winreg.QueryValueEx(key, "Personal")
        winreg.CloseKey(key)
        if path:
            # Expand any environment variables (e.g., %USERPROFILE%)
            path = os.path.expandvars(path)
            path = os.path.normpath(path)
            if os.path.isdir(path):
                return path
    except (OSError, FileNotFoundError):
        pass

    # Fallback
    return os.path.join(os.environ.get("USERPROFILE", os.environ.get("HOMEDRIVE", "C:") + os.environ.get("HOMEPATH", "")), "Documents")


DOCUMENTS_PATH = get_documents_path()
CONFIG_DIR = os.path.join(DOCUMENTS_PATH, "ETS2 Translator")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")



# ── Prompt loading from external files ──

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = os.path.join(_PROMPTS_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_receive_prompt() -> str:
    """Get the English→Chinese translation prompt."""
    prompt = load_prompt("receive_prompt.txt")
    if not prompt:
        return (
            "You are a translator for ETS2/TruckersMP in-game chat. "
            "Translate ALL messages into natural, accurate Simplified Chinese. "
            "Never summarize, never omit, never add — TRANSLATE ONLY."
        )
    return prompt


def get_send_prompt() -> str:
    """Get the Chinese→English translation prompt."""
    prompt = load_prompt("send_prompt.txt")
    if not prompt:
        return (
            "You are a translator for ETS2/TruckersMP in-game chat. "
            "Translate Chinese into natural, accurate English that a real gamer would type. "
            "Never summarize, never omit, never add. Output ONLY the English translation."
        )
    return prompt


DEFAULT_SYSTEM_PROMPT = get_receive_prompt()


@dataclass
class ProviderConfig:
    """A single LLM provider configuration."""
    label: str = ""
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True


@dataclass
class AppConfig:
    api_endpoint: str = ""
    api_key: str = ""
    api_model: str = ""
    target_language: str = "zh-CN"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    window_opacity: float = 0.80
    font_size: int = 12
    max_messages: int = 50
    player_name: str = ""  # auto-detected or manually set in-game name
    window_mode: str = "standalone"  # "standalone" or "overlay"
    click_through: bool = False  # only in overlay mode
    win_x: int = -1  # saved window x, -1 means auto-center
    win_y: int = -1  # saved window y
    win_w: int = 620  # saved window width
    win_h: int = 360  # saved window height
    settings_win_w: int = 540  # settings dialog width
    settings_win_h: int = 700  # settings dialog height
    chat_hotkey: str = "y"      # hotkey to open in-game chat window
    copy_hotkey: str = "ctrl+c"  # hotkey to copy translated text to clipboard
    paste_hotkey: str = "ctrl+v" # hotkey to paste (Ctrl+V) into game
    enter_hotkey: str = "enter"  # hotkey to press Enter in game
    send_hotkey: str = "shift+y" # global hotkey to focus translator input
    translation_backend: str = "llm"  # "llm" or "baidu"
    baidu_appid: str = ""   # Baidu Translate APP ID
    baidu_secret: str = ""  # Baidu Translate secret key
    debug_log: bool = False  # enable debug logging to %TEMP%
    llm_providers: list[dict] = field(default_factory=list)  # NEW: list of provider dicts


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config():
    ensure_config_dir()
    if not os.path.exists(CONFIG_PATH):
        cfg = AppConfig()
        save_config(cfg)
        return cfg

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    defaults = asdict(AppConfig())
    # Merge loaded data over defaults (allow partial configs)
    merged = {**defaults, **data}
    # Decrypt sensitive fields
    for field in _SECRET_FIELDS:
        if field in merged and isinstance(merged[field], str):
            merged[field] = _maybe_decrypt(field, merged[field])

    # Decrypt sensitive fields in providers
    for provider in merged.get("llm_providers", []):
        if "api_key" in provider and isinstance(provider["api_key"], str):
            provider["api_key"] = _maybe_decrypt("api_key", provider["api_key"])

    # Migration: if llm_providers is empty but old api_endpoint is set, create one provider
    if not merged.get("llm_providers") and merged.get("api_endpoint"):
        merged["llm_providers"] = [{
            "label": "LLM Provider",
            "endpoint": merged["api_endpoint"],
            "api_key": merged["api_key"],
            "model": merged["api_model"],
            "enabled": True,
        }]
    cfg = AppConfig(**{k: merged[k] for k in defaults})
    return cfg


def save_config(cfg: AppConfig):
    ensure_config_dir()
    data = asdict(cfg)
    # Encrypt sensitive fields before writing
    for field in _SECRET_FIELDS:
        if field in data and isinstance(data[field], str):
            data[field] = _maybe_encrypt(field, data[field])

    # Encrypt sensitive fields in providers
    for provider in data.get("llm_providers", []):
        if "api_key" in provider and isinstance(provider["api_key"], str):
            provider["api_key"] = _maybe_encrypt("api_key", provider["api_key"])

    # Sync first provider to legacy flat fields for backward compat
    if data.get("llm_providers"):
        first = data["llm_providers"][0]
        data["api_endpoint"] = first.get("endpoint", "")
        data["api_key"] = first.get("api_key", "")
        data["api_model"] = first.get("model", "")
    content = json.dumps(data, indent=2, ensure_ascii=False)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(content)
    except PermissionError:
        _atomic_save(content)


def _atomic_save(content: str):
    fd = -1
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=CONFIG_DIR, prefix="config_", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        fd = -1
        os.replace(tmp_path, CONFIG_PATH)
    except OSError:
        _fallback_save(content)
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _fallback_save(content: str):
    alt_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.environ["USERPROFILE"]), "ETS2 Translator")
    os.makedirs(alt_dir, exist_ok=True)
    alt_path = os.path.join(alt_dir, "config.json")
    with open(alt_path, "w", encoding="utf-8") as f:
        f.write(content)
