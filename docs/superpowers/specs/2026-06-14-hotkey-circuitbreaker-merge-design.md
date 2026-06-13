# Hotkey + Provider Circuit Breaker + Request Merging Design

> **日期:** 2026-06-14 | **状态:** Draft

## 一、RegisterHotKey 系统热键

### 现状
`hotkey_manager.py` 用 `GetAsyncKeyState` 每 50ms 轮询检测按键。偶发被游戏吞掉。

### 方案
改用 Windows `RegisterHotKey` API，在隐藏消息窗口中注册系统级热键，收到 `WM_HOTKEY` 消息后回调。

### 实现
```python
class HotkeyManager:
    def __init__(self, root, cfg, focus_callback):
        # ... 现有初始化 ...
        self._hotkey_thread = None
        self._hwnd = None          # 隐藏消息窗口句柄
        self._hotkey_id = 1

    def _create_hotkey_window(self):
        """创建隐藏的消息窗口，向 Windows 注册系统级热键"""
        # RegisterClassExW + CreateWindowExW 创建隐藏窗口
        # RegisterHotKey(self._hwnd, 1, mods, vk)
        # 消息循环中捕获 WM_HOTKEY → focus_callback

    def start(self):
        """启动热键监听线程（消息循环）"""
        # 在独立线程中运行 GetMessageW 消息循环

    def stop(self):
        """停止热键监听"""
        # UnregisterHotKey + PostQuitMessage + 线程 join
```

### 影响
- `hotkey_manager.py` 重写核心逻辑
- 不影响 `_parse_hotkey()` 和 `update_send_hotkey()` 等其他方法
- overlay.py 调用方式不变

## 二、Provider 熔断器

### 现状
Provider 并行竞速失败 → 串行重试一次。同一个挂了的 Provider 会反复被重试。

### 方案
每个 Provider 增加健康状态追踪：
- `failures`: 连续失败次数
- `cool_until`: 冷却到什么时候
- 连续失败 ≥ 3 次 → 冷却 30s，期间跳过
- 冷却结束重试成功 → 清零恢复
- 冷却结束重试仍失败 → 冷却翻倍（30s → 60s → 120s 上限）

### 实现位置
`translator.py` 中 `Translator` 类增加：

```python
class ProviderHealth:
    failures: int = 0
    cool_until: float = 0  # time.monotonic() timestamp

class Translator:
    def __init__(self, ...):
        self._provider_health = {}  # label -> ProviderHealth

    def _call_api(self, text):
        # 过滤掉冷却中的 Provider
        active = [p for p in providers if not self._is_cooling(p)]
        if not active:
            # 全部冷却 → 放宽限制，全试用
            active = providers

    def _is_cooling(self, provider):
        health = self._provider_health.get(provider["label"])
        if health and time.monotonic() < health.cool_until:
            return True
        return False

    def _note_result(self, provider_label, success):
        health = self._provider_health[provider_label]
        if success:
            health.failures = 0
            health.cool_until = 0
        else:
            health.failures += 1
            if health.failures >= 3:
                duration = min(30 * (2 ** (health.failures - 3)), 120)
                health.cool_until = time.monotonic() + duration
```

### 日志
- `[LLM] Provider DeepSeek 进入冷却 30s（连续 3 次失败）`
- `[LLM] Provider DeepSeek 冷却结束，重试成功，已恢复`

## 三、同文本请求合并

### 现状
相同文本并发到达时，各自独立发起 API 请求。虽然 LRU 缓存覆盖了大部分场景，但冷启动或缓存已满时会有并发重复。

### 方案
`in_flight` 字典 + `threading.Event`：

```python
class Translator:
    def __init__(self, ...):
        self._in_flight = {}        # text -> Event
        self._in_flight_results = {}  # text -> result
        self._in_flight_lock = threading.Lock()

    def _call_api(self, text):
        # 1. 检查是否已有请求在进行
        with self._in_flight_lock:
            if text in self._in_flight:
                event = self._in_flight[text]
                # 等待已有请求完成
                event.wait(timeout=10)
                return self._in_flight_results.get(text, text)
            # 2. 标记为进行中
            self._in_flight[text] = threading.Event()

        try:
            result = self._do_translate(text)  # 实际翻译
            with self._in_flight_lock:
                self._in_flight_results[text] = result
            return result
        finally:
            with self._in_flight_lock:
                self._in_flight[text].set()  # 唤醒所有等待者
                del self._in_flight[text]
```

## 四、文件变更

| 文件 | 动作 | 说明 |
|:---|:---|:---|
| `hotkey_manager.py` | 重写核心 | RegisterHotKey + 消息循环替代轮询 |
| `translator.py` | 修改 | Provider 熔断 + 请求合并 |

## 五、非功能约束
- 不新增第三方依赖
- 热键变更后自动重注册
- 熔断日志写入 logger
- 请求合并超时 10s 防止死锁
