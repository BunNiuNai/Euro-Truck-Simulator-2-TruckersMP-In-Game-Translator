"""
Auto-update: checks GitHub Releases, downloads new exe, replaces via batch script.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
import threading
from urllib.request import urlopen, urlretrieve
from urllib.error import URLError

from config import VERSION
from logger import get_logger

GITHUB_API = "https://api.github.com/repos/BunNiuNai/ets2-translator/releases/latest"

# GitHub download mirrors for Chinese users (tried in order after direct access fails)
_DOWNLOAD_MIRRORS = [
    "https://ghproxy.com/",
    "https://gh-proxy.com/",
]


def _fetch_json(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from URL. Returns parsed dict or None on failure."""
    try:
        req = urlopen(url, timeout=timeout)
        return json.loads(req.read().decode())
    except (URLError, OSError, json.JSONDecodeError):
        return None


def check_for_update() -> tuple[bool, str, str]:
    """Query GitHub latest release. Tries direct then mirrors.
    Returns (has_update, version, download_url) or (False, "", "")."""
    # Try direct GitHub API first
    data = _fetch_json(GITHUB_API)
    source = "GitHub"

    # Fall back to mirrors
    if data is None:
        for mirror in _DOWNLOAD_MIRRORS:
            data = _fetch_json(f"{mirror}{GITHUB_API}", timeout=15)
            if data is not None:
                source = f"镜像 {mirror}"
                break

    if data is None:
        log = get_logger()
        if log:
            log.warn("UPD", "检查更新失败: 无法连接到 GitHub（直连和镜像均失败）")
        return False, "", ""

    latest = data.get("tag_name", "")
    if not latest:
        return False, "", ""

    if _version_newer(latest, VERSION):
        url = ""
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".exe"):
                url = asset.get("browser_download_url", "")
                break
        log = get_logger()
        if log:
            log.info("UPD", f"发现新版本: {latest} (via {source})")
        return True, latest, url
    # No update available
    log = get_logger()
    if log:
        log.info("UPD", f"已是最新版本: {VERSION} (via {source})")
    return False, latest, ""


def _version_newer(latest: str, current: str) -> bool:
    """Compare 'v1.0.8' > 'v1.0.7'."""
    def parse(v: str) -> tuple[int, ...]:
        v = v.strip().lstrip("v")
        parts = v.split(".")
        return tuple(int(p) for p in parts if p.isdigit())
    try:
        return parse(latest) > parse(current)
    except (ValueError, IndexError):
        return False


def download_update(url: str, progress_cb: callable | None = None) -> str | None:
    """Download new exe to a temp path. Tries direct URL then mirrors.
    progress_cb(percent: int) is called during download.
    """
    tmp = tempfile.mktemp(suffix=".exe", prefix="ets2_update_")
    log = get_logger()

    urls_to_try = [url] + [f"{m}{url}" for m in _DOWNLOAD_MIRRORS]
    for i, try_url in enumerate(urls_to_try):
        try:
            source = "直连" if i == 0 else f"镜像 {_DOWNLOAD_MIRRORS[i-1]}"
            if log:
                log.info("UPD", f"开始下载更新 ({source})")
            _download_with_progress(try_url, tmp, progress_cb)
            if log:
                log.info("UPD", f"更新下载完成 ({source})")
            return tmp
        except (URLError, OSError) as e:
            if log:
                log.warn("UPD", f"下载失败 ({source}): {e}")
            continue

    if progress_cb:
        progress_cb(-1)
    if log:
        log.error("UPD", "下载失败: 所有下载源均不可用")
    return None


def _download_with_progress(url: str, dest: str, progress_cb: callable | None = None) -> None:
    """Download file with progress callback."""
    resp = urlopen(url, timeout=60)
    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    block_size = 8192

    with open(dest, "wb") as f:
        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total > 0:
                progress_cb(int(downloaded * 100 / total))

    if total > 0 and downloaded < total * 0.95:
        raise OSError("Download incomplete")


def apply_update(new_exe_path: str, own_exe_path: str) -> None:
    """Create and launch a batch script that replaces the running exe after exit.
    Called right before sys.exit()."""
    log = get_logger()
    if log:
        log.info("UPD", f"安装更新: {os.path.basename(new_exe_path)} → {os.path.basename(own_exe_path)}")
    bat = os.path.join(tempfile.gettempdir(), "ets2_update.bat")

    with open(bat, "w", encoding="ascii") as f:
        f.write("@echo off\r\n")
        f.write(":loop\r\n")
        f.write(f'tasklist /fi "PID eq {os.getpid()}" 2>nul | find "{os.getpid()}" >nul\r\n')
        f.write("if not errorlevel 1 (\r\n")
        f.write("    ping 127.0.0.1 -n 2 >nul\r\n")
        f.write("    goto loop\r\n")
        f.write(")\r\n")
        f.write(f'move /Y "{new_exe_path}" "{own_exe_path}"\r\n')
        f.write(f'start "" "{own_exe_path}"\r\n')
        f.write(f'del "{bat}"\r\n')

    # Launch batch detached
    ctypes.windll.shell32.ShellExecuteW(None, "open", bat, None, None, 0)
