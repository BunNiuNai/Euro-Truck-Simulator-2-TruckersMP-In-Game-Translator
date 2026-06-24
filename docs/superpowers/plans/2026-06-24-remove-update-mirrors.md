# Remove Update Mirrors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove GitHub mirror download support from update.py and README, keeping only direct GitHub download.

**Architecture:** Surgical deletion only — remove `_DOWNLOAD_MIRRORS` list, mirror fallback loops in `check_for_update()` and `download_update()`, and mirror-related text in README. No new code, no interface changes.

**Tech Stack:** Python 3.10+ (update.py), Markdown (README.md)

---

### Task 1: Remove mirrors from update.py

**Files:**
- Modify: `ets2-translator/update.py`

- [ ] **Step 1: Delete `_DOWNLOAD_MIRRORS` list (lines 21-24)**

```python
# DELETE these 4 lines:
_DOWNLOAD_MIRRORS = [
    "https://ghproxy.com/",
    "https://gh-proxy.com/",
]
```

- [ ] **Step 2: Simplify `check_for_update()` — remove mirror fallback loop**

Replace lines 39-55 (from `data = _fetch_json(GITHUB_API)` to `return False, "", ""`):

```python
    data = _fetch_json(GITHUB_API)
    if data is None:
        log = get_logger()
        if log:
            log.warn("UPD", "检查更新失败: 无法连接到 GitHub")
        return False, "", ""
```

And update the log messages at lines 69 and 74 to remove `(via {source})`:

```python
# line 69: Change to:
            log.info("UPD", f"发现新版本: {latest}")
# line 74: Change to:
        log.info("UPD", f"已是最新版本: {VERSION}")
```

Also remove the `source` variable assignment (line 41: `source = "GitHub"`).

- [ ] **Step 3: Simplify `download_update()` — remove mirror URL loop**

Replace lines 90-116 (from `def download_update` to `return None`):

```python
def download_update(url: str, progress_cb: callable | None = None) -> str | None:
    """Download new exe to a temp path. Returns path or None on failure.
    progress_cb(percent: int) is called during download.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".exe", prefix="ets2_update_", delete=False).name
    log = get_logger()

    try:
        if log:
            log.info("UPD", "开始下载更新")
        _download_with_progress(url, tmp, progress_cb)
        if log:
            log.info("UPD", "更新下载完成")
        return tmp
    except (URLError, OSError) as e:
        if log:
            log.warn("UPD", f"下载失败: {e}")
        if progress_cb:
            progress_cb(-1)
        if log:
            log.error("UPD", "下载失败")
        return None
```

- [ ] **Step 4: Clean up unused import**

The `tempfile` import on line 10 is already used by `apply_update()` through `tempfile.gettempdir()`. Check if `tempfile.NamedTemporaryFile` is still used in `download_update()` — yes it is (the `tmp = tempfile.NamedTemporaryFile(...)` line). No imports to remove.

- [ ] **Step 5: Verify syntax**

Run: `python -m py_compile ets2-translator/update.py`
Expected: No output (compiles cleanly)

- [ ] **Step 6: Commit**

```bash
git add ets2-translator/update.py
git commit -m "refactor: remove GitHub mirror download support from update.py

Remove _DOWNLOAD_MIRRORS list, mirror fallback loops in check_for_update()
and download_update(). Keep only direct GitHub download.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Remove mirror references from README.md

**Files:**
- Modify: `ets2-translator/README.md`

- [ ] **Step 1: Update auto-update feature description (line 104)**

Change:
```
| 🔄 | **一键自动更新** | 启动检查 GitHub 新版本 + 国内镜像下载支持 |
```
To:
```
| 🔄 | **一键自动更新** | 启动检查 GitHub 新版本，自动下载更新 |
```

- [ ] **Step 2: Remove mirror download feature row (line 105)**

Delete the entire line:
```
| 🌏 | **GitHub 镜像下载** | 国内用户自动走 ghproxy.com 代理，无障碍更新 |
```

- [ ] **Step 3: Remove FAQ entry "国内用户如何下载更新？" (lines 406-410)**

Delete these 5 lines:
```
<details>
<summary>🟢 <b>国内用户如何下载更新？</b></summary>

> v1.2.3 起内置 GitHub 镜像下载支持，自动通过 ghproxy.com 代理，国内直连无障碍。
</details>
```

- [ ] **Step 4: Commit**

```bash
git add ets2-translator/README.md
git commit -m "docs: remove mirror download references from README

Remove GitHub mirror download feature description and FAQ entry.
Keep only direct GitHub download.

Co-Authored-By: Claude <noreply@anthropic.com>"
```
