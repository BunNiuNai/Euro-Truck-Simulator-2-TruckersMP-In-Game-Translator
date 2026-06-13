# Multi-Provider Fallback + Hot-Reload + Speed Optimization Design

> **日期:** 2026-06-14 | **状态:** Approved

## 目标

1. **多 LLM Provider 回退**：支持配置多个 LLM API，并行竞速 + 失败回退
2. **配置热重载**：监控配置文件变化，自动重载翻译引擎
3. **翻译加速**：缩短批量窗口、快速失败、并行请求、增大缓存

---

## 一、翻译加速

| 优化项 | 当前值 | 新值 |
|:---|:---|:---|
| `BATCH_WINDOW` | 0.8s | **0.3s** |
| HTTP timeout | 30s | **8s** |
| `CACHE_SIZE` | 200 | **1000** |
| Provider 策略 | 串行 | **并行竞速 + 串行回退** |

### 并行竞速逻辑

```
收到翻译请求（缓存未命中）
  ├─ 第一轮：ThreadPoolExecutor 并行向所有 enabled Provider 发请求
  │   └─ 谁先成功返回就用谁的结果，忽略其余
  └─ 第一轮全部失败 → 等待 180ms
       └─ 第二轮：串行重试每个 Provider（每个一次）
            └─ 全部失败 → 返回错误
```

百度混合监督模式不变：LLM 结果出来后，再走百度对比纠错。

---

## 二、多 Provider 配置

### 配置格式

新增 `llm_providers` 数组（向下兼容）：

```json
{
  "llm_providers": [
    {
      "label": "DeepSeek",
      "endpoint": "https://api.deepseek.com/v1/chat/completions",
      "api_key": "sk-xxx",
      "model": "deepseek-chat",
      "enabled": true
    }
  ],
  "translation_backend": "llm",
  "baidu_appid": "",
  "baidu_secret": ""
}
```

### 向下兼容

- 加载配置时，如 `llm_providers` 为空且旧字段 `api_endpoint` 非空，自动迁移
- 保存时同步更新旧字段为第一个 provider 的值

### AppConfig 模型变更

```python
@dataclass
class ProviderConfig:
    label: str = ""
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = True

@dataclass  
class AppConfig:
    llm_providers: list[dict] = field(default_factory=list)  # NEW
    # ... api_endpoint/api_key/api_model 保留作为兼容字段 ...
```

---

## 三、配置热重载

### 机制

- 在 Translator 消息循环中，每 3 秒检查 `config.json` 的 mtime
- 变化时：重新 load → 更新 cfg → 重建 httpx.Client → 写日志 "配置已热重载"

### 参考

对方 Seven-TMP 项目在 `CheckConfigReload()` 中使用 `GetFileAttributesExW` 获取 `ftLastWriteTime`，Python 直接用 `os.path.getmtime()` 即可。

---

## 四、设置界面变更

API 标签页改造为 Provider 列表：

- 每个 Provider 显示为可折叠卡片，含 endpoint/model/API Key
- 支持 ↑↓ 排序（影响回退优先级）、✕ 删除
- `[+ 添加 Provider]` 按钮
- `enabled` 复选框
- 百度翻译保留为独立区块
- `[Test All / 测试全部]` 测试所有 enabled Provider + 百度

---

## 五、文件变更

| 文件 | 动作 | 说明 |
|:---|:---|:---|
| `config.py` | 修改 | 新增 `llm_providers` 字段 + 迁移逻辑 |
| `translator.py` | 修改 | 并行竞速 + 缩短窗口 + 大缓存 + 热重载 |
| `main.py` | 修改 | 设置界面 Provider 列表 UI |

---

## 六、非功能约束

- HTTP 超时降低后仍保持 8s（兼顾网络差的用户）
- 并行请求使用 ThreadPoolExecutor，与现有百度并行逻辑一致
- 热重载不增加额外线程，在现有消息循环中检查
- 不新增第三方依赖
