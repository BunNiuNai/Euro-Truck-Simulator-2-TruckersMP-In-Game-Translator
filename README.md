# 🚛 ETS2 TruckersMP Chat Translator · 欧卡联机聊天翻译器

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.3.0-3b82f6?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-10b981?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?style=for-the-badge&logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python" alt="Python">
</p>

<p align="center">
  <img src="https://img.shields.io/github/downloads/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator/total?style=flat-square&color=3b82f6" alt="Downloads">
  <img src="https://img.shields.io/github/stars/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator?style=flat-square&color=f59e0b" alt="Stars">
  <img src="https://img.shields.io/github/last-commit/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator?style=flat-square&color=64748b" alt="Last Commit">
</p>

<p align="center">
  <strong>🌍 实时多语言聊天翻译 · 悬浮窗口 · 一键发送 · 零依赖</strong><br>
  <sub>Real-time in-game chat translator for Euro Truck Simulator 2 / TruckersMP</sub>
</p>

<p align="center">
  <a href="https://github.com/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator/releases"><b>⬇️ 下载 Exe</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-quick-start--快速开始"><b>🚀 快速开始</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-features--功能特性"><b>✨ 功能特性</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-faq--常见问题"><b>❓ 常见问题</b></a>
</p>

---

> 🚛 在 ETS2 TruckersMP 联机中，自动将各国语言聊天实时翻译为简体中文，以半透明悬浮窗显示。
> 支持中文打字 → 自动翻译为英文 → 一键发送到游戏聊天。**完全免费 · 开源 · 无需安装 Python**

---

## 📖 目录

- [✨ 功能特性](#-features--功能特性)
- [🆕 v1.3.0 更新亮点](#-v130-更新亮点)
- [🧠 推荐大模型](#-recommended-llm--推荐大模型)
- [🖥 系统要求](#-system-requirements--系统要求)
- [🚀 快速开始](#-quick-start--快速开始)
- [⚙️ 配置说明](#️-configuration--配置说明)
- [📖 使用方式](#-usage--使用方式)
- [🔧 运行原理](#-how-it-works--运行原理)
- [📁 项目结构](#-project-structure--项目结构)
- [❓ 常见问题](#-faq--常见问题)
- [📄 许可证](#-license--许可证)

---

## ✨ Features · 功能特性

### 🌐 核心翻译

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 🌐 | **实时聊天翻译** | 监控 TruckersMP 聊天日志，批量翻译各国语言 → 简体中文 |
| 📤 | **反向翻译发送** | 输入中文 → 自动翻译英文 → 热键发送到游戏聊天 |
| 🔤 | **系统消息翻译** | TMP 系统通知（服务器重启、玩家连接等）也会被翻译 |
| 👥 | **全员翻译模式** | 所有玩家消息均等翻译，自动识别自己的消息跳过不译 |
| 🎯 | **游戏昵称识别** | 自动检测或手动填写你的游戏文字昵称，区分自己和他人的消息 |

### 🧠 智能翻译引擎

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 🏎️ | **多 Provider 并行竞速** | 配置多个大模型 API，同时发起请求，**谁快用谁** |
| 🔄 | **Provider 熔断回退** | 连续失败 3 次自动冷却，成功恢复；全部失败串行重试 |
| 📦 | **批量翻译** | 0.3 秒窗口收集多条消息，合并为一次 API 请求 |
| 💾 | **LRU 缓存 1000 条** | 重复消息直接命中缓存，零延迟零消耗 |
| 🔀 | **三种翻译后端** | LLM / 百度翻译 / LLM+百度监督混合模式 |
| 🛡️ | **百度翻译监督** | LLM 先翻译 → 百度对比纠错 → 不一致自动替换 |
| 📊 | **同文本请求合并** | 相同原文并发到达时自动合并为一次 API 调用 |
| 🔐 | **DPAPI 加密存储** | API Key 使用 Windows 系统级加密，配置文件不暴露明文 |

### 🪟 窗口与交互

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 🪟 | **双窗口模式** | 标准窗口 / 无边框悬浮窗（支持鼠标穿透 + 边缘拖拽缩放） |
| 🎨 | **VS Code 深灰主题** | 精致的深色设置界面，与悬浮窗风格统一 |
| ⌨️ | **系统级全局热键** | RegisterHotKey 系统热键，不会被游戏拦截 |
| 📋 | **系统托盘图标** | 右键托盘菜单：显示/隐藏、切换模式、鼠标穿透、设置、退出 |
| 🕐 | **北京时间显示** | 悬浮窗底部实时显示北京时间 |
| 🪟 | **窗口圆角** | Win11 原生圆角 + Win10 SetWindowRgn 兼容 |
| 📍 | **窗口位置记忆** | 自动保存和恢复悬浮窗和设置窗口位置与大小 |

### 📋 日志与诊断

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 📋 | **翻译器日志** | 系统事件、API 连通、错误详情、TMP 监控、周期统计 |
| 💬 | **消息日志** | 已翻译的聊天记录，原文和译文并排查看 |
| 📂 | **自动写入文件** | 日志保存到 Documents\ETS2 Translator\logs\，自动轮转 |
| 🔍 | **一键测试全部** | 测试所有 Provider + 百度翻译的连通性 |

### 🔧 其他

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 🔄 | **一键自动更新** | 启动检查 GitHub 新版本 + 国内镜像下载支持 |
| 🌏 | **GitHub 镜像下载** | 国内用户自动走 ghproxy.com 代理，无障碍更新 |
| 🔥 | **配置热重载** | 修改配置文件 3 秒自动生效，无需重启 |
| 💬 | **游戏术语库** | 内置 130+ 行 ETS2 专用术语 + 100+ 条网游俚语 |
| ✂️ | **消息分割线** | 每条翻译消息下方分隔线，快速区分 |
| 🚫 | **聊天去重** | 同一条消息（玩家+内容+时间戳）不重复显示 |
| 🎛️ | **10 种目标语言** | 简体中文 / English / 日本語 / 한국어 / Français / Deutsch / Español / Русский / Português / Italiano |

---

## 🆕 v1.3.0 更新亮点

<details open>
<summary><b>点击展开完整更新日志</b></summary>

### 🌐 多 LLM Provider 并行回退
- 配置多个大模型 API，翻译时**并行竞速**，最快的结果立即返回
- Provider 连续失败 3 次自动**熔断冷却**，成功后自动恢复
- **同文本并发请求自动合并**，节省 API 费用
- 设置界面支持 Provider 增删改排序

### ⚡ 翻译加速
- 批量等待窗口 0.8s → **0.3s**
- HTTP 超时 30s → **8s**
- LRU 缓存 200 条 → **1000 条**
- Provider 策略从单路串行升级为**多路并行竞速**

### 🔄 配置热重载
- 修改配置文件后 3 秒自动检测并重载翻译引擎，无需重启程序

### ⌨️ 系统热键改进
- 从轮询升级为 **RegisterHotKey 系统级热键**
- 多策略焦点激活（AllowSetForegroundWindow + 模拟 Alt 键 + SetActiveWindow）

### 🎨 界面优化
- VS Code 深灰主题配色 + 语言下拉框可读名称 + 输入框随窗口拉伸

### 🪟 窗口增强
- 翻译器窗口圆角 + 底部状态栏北京时间时钟

### 📋 日志分拆
- 翻译器日志 + 消息日志两个独立标签页

### 🔤 系统消息翻译
- TMP 系统通知现在也会被翻译

### 🐛 Bug 修复
- 修复设置界面多个交互问题 + 消息请求合并死锁 + 输入框拉伸失效

</details>

---

## 🧠 Recommended LLM · 推荐大模型

> 💡 任意兼容 OpenAI API 格式的服务均可使用，填写地址、密钥和模型名即可。

| 🏢 提供商 | 🤖 推荐模型 | 💰 价格 | 📝 备注 |
|:---|:---|:---|:---|
| 🏔️ [SiliconFlow 硅基流动](https://siliconflow.cn/) | `Qwen/Qwen3-8B` | 🆓 免费额度 | 国内直连，不限并发 |
| 🐋 [DeepSeek](https://platform.deepseek.com/) | `deepseek-chat` | ¥1/1M tokens | 翻译质量极佳 |
| 🤖 [OpenAI](https://platform.openai.com/) | `gpt-4o-mini` | $0.15/1M tokens | 便宜可靠 |
| ⚡ [Groq](https://groq.com/) | `llama-3.3-70b` | 🆓 免费额度 | 推理速度极快 |
| 🏠 [Ollama](https://ollama.com/) | `qwen3:8b` | 🆓 本地免费 | 无需网络，隐私安全 |

> 🔥 **国内用户推荐**：硅基流动 + Qwen3-8B，免费额度、国内直连、速度快。
>
> 🌍 **海外用户推荐**：OpenAI gpt-4o-mini 或 DeepSeek，便宜且翻译质量高。

---

## 🖥 System Requirements · 系统要求

| 📋 项目 | 📝 要求 |
|:---|:---|
| 🪟 **操作系统** | Windows 10 / 11（64 位） |
| 🐍 **Python** | 3.10+（exe 打包版无需安装） |
| 🎮 **游戏** | Euro Truck Simulator 2 + TruckersMP 联机模组 |

---

## 🚀 Quick Start · 快速开始

### 方式一：📦 下载 exe 直接运行（推荐）

从 [📥 GitHub Releases](https://github.com/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator/releases) 下载最新 `ETS2-TruckersMP翻译器.exe`，双击运行即可。

> ✅ 无需安装 Python · 无需配置环境 · 开箱即用

### 方式二：🐍 Python 源码运行

```bash
# 1️⃣ 克隆仓库
git clone https://github.com/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator.git
cd Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator

# 2️⃣ 安装依赖（仅 httpx 一个包）
pip install -r requirements.txt

# 3️⃣ 运行
python main.py
```

### 方式三：🔨 自行打包

```bash
python build_exe.py
# 输出 → dist/ETS2-TruckersMP翻译器.exe
```

---

## ⚙️ Configuration · 配置说明

> 🔰 首次运行自动弹出设置窗口，也可通过系统托盘右键 → **Settings / 设置** 打开。

### 🌐 Provider 配置（多 LLM 支持）

| ⚙️ 配置项 | 📝 说明 | 💡 示例 |
|:---|:---|:---|
| 🏷️ **Label** | Provider 名称 | `DeepSeek` |
| 🔗 **Endpoint** | API 地址（**必须包含完整路径**） | `https://api.deepseek.com/v1/chat/completions` |
| 🔑 **API Key** | API 密钥 | `sk-xxxxxxxx` |
| 🤖 **Model** | 模型名称 | `deepseek-chat` |
| ✅ **Enabled** | 启用/禁用此 Provider | ☑ |

> ⚠️ Endpoint 必须是完整 URL，例如 `https://api.siliconflow.cn/v1/chat/completions`，只填 `https://api.siliconflow.cn/v1` 会导致连接失败。

### ⚙️ 其他配置

| ⚙️ 配置项 | 📝 说明 | 💡 示例 |
|:---|:---|:---|
| 🔀 **翻译后端** | LLM / 百度 / LLM+百度混合 | `LLM + 百度监督` |
| 🌐 **目标语言** | 翻译目标语言 | `简体中文` |
| 🔤 **百度 APP ID** | 百度翻译 API 的 APP ID | `1234567899887654` |
| 🔐 **百度 Secret** | 百度翻译 API 的密钥 | `xxxxxx` |
| 🎨 **窗口透明度** | 0.10 ~ 1.00 | `0.80` |
| 🔤 **字体大小** | 聊天显示字体大小 | `12` |
| 📊 **最大消息数** | 窗口可见最大消息条数 | `50` |
| 🎮 **游戏昵称** | 你的游戏内文字昵称（自动检测） | `PlayerName` |
| 🪟 **窗口模式** | 标准 / 悬浮 | `Overlay 悬浮` |
| 🖱️ **鼠标穿透** | 点击穿透到游戏（仅悬浮模式） | `否` |
| ⌨️ **复制热键** | 复制译文到剪贴板 | `ctrl+c` |
| ⌨️ **发送热键** | 确认消息已发送 | `enter` |
| ⌨️ **呼出热键** | 全局热键呼出输入框 | `shift+y` |

### ⌨️ 热键设置

点击设置中的热键输入框 → 显示 **"按下组合键..."** → 直接按下键盘组合键 → 自动识别保存。

> ⚠️ **绑定热键前请关闭 Caps Lock 大写锁定！**

---

## 📖 Usage · 使用方式

1. 🎮 启动 ETS2 并进入 TruckersMP 联机服务器
2. 🚛 运行翻译器 → 窗口以悬浮或标准模式显示
3. 👀 **查看翻译**：其他玩家消息自动翻译显示在窗口中
4. ✍️ **发送消息**：
   - 按全局热键（默认 `Shift+Y`）呼出输入栏
   - 输入中文 → 回车 → 自动翻译为英文
   - 翻译结果自动选中 → 按复制热键复制到剪贴板
   - 在游戏中打开聊天框粘贴（`Ctrl+V`）→ 按发送热键确认
5. 🖱️ 右键系统托盘图标进行快捷操作（显示/隐藏、切换模式、鼠标穿透等）

---

## 🔧 How It Works · 运行原理

```
┌──────────────────────────────────────────────────────────────┐
│                     🎮 ETS2 / TruckersMP                      │
│   游戏聊天 ──→ 写入日志 chat_YYYY-MM-DD_log.txt               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼ (增量读取，0.5s 轮询)
┌──────────────────────────────────────────────────────────────┐
│  📡 monitor.py — 聊天日志监控                                  │
│  · 注册表读取 Documents 路径                                   │
│  · 正则匹配聊天行 + 系统消息行                                   │
│  · 去重 + 自动识别玩家昵称                                      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼ (raw_queue, maxsize=500)
┌──────────────────────────────────────────────────────────────┐
│  🧠 translator.py — 翻译引擎                                   │
│  · LRU 缓存 1000 条 → 命中直接返回                             │
│  · 批量模式：0.3s 窗口收集消息                                  │
│  · 多 Provider 并行竞速 + 熔断回退                              │
│  · 三种后端：LLM / 百度 / LLM+百度混合                          │
│  · 配置热重载：3 秒检测文件变化                                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼ (display_queue, maxsize=500)
┌──────────────────────────────────────────────────────────────┐
│  🪟 overlay.py — 翻译显示窗口                                  │
│  · 每 250ms 轮询队列                                           │
│  · 双模式：标准窗口 / 无边框悬浮                                 │
│  · Win32 API 鼠标穿透 + 拖拽 + 边缘缩放                         │
│  · RegisterHotKey 系统热键呼出输入栏                            │
│  · API 统计 + 北京时间                                          │
│  · 窗口位置/大小自动记忆                                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure · 项目结构

```
📁 ets2-translator/
├── 🚀 main.py              # 入口、主控、设置对话框
├── ⚙️ config.py             # 配置模型、DPAPI 加密、JSON 读写
├── 📡 monitor.py           # TMP 聊天日志监控（增量轮询、正则解析）
├── 🧠 translator.py        # 翻译引擎（多Provider并行、熔断、缓存、批量）
├── 🪟 overlay.py           # 显示窗口（Tkinter + Win32 API、输入栏、热键）
├── ⌨️ hotkey_manager.py     # 系统热键管理（RegisterHotKey + 消息窗口）
├── 📨 input_sender.py      # 键盘模拟（SendInput API、剪贴板）
├── 📋 tray_icon.py         # 系统托盘（纯 ctypes + Win32 API）
├── 🔄 update.py            # 自动更新（GitHub 版本检查 + 镜像下载）
├── 🏗️ build_exe.py          # PyInstaller 打包脚本
├── 📊 win32_constants.py   # Win32 常量/结构体共享模块
├── 💬 message_display.py   # 消息渲染引擎
├── 📦 message_types.py     # 数据类（DisplayMessage / TranslationStats）
├── 📝 logger.py            # 日志模块（文件轮转 + 内存缓冲）
├── 📄 requirements.txt     # Python 依赖（仅 httpx）
├── 🎨 icon.ico             # 程序图标
└── 📦 dist/                # 构建输出
    └── ETS2-TruckersMP翻译器.exe
```

---

## ❓ FAQ · 常见问题

<details>
<summary>🔴 <b>翻译显示"[网络错误] 无法连接到 API 服务器"？</b></summary>

> 检查 API Endpoint 地址是否正确。**必须包含完整路径**，如 `https://api.deepseek.com/v1/chat/completions`，只填 `https://api.deepseek.com/v1` 会导致 404。
</details>

<details>
<summary>🔴 <b>翻译显示"[认证失败] API 密钥无效"？</b></summary>

> 检查 API Key 是否正确填写，密钥是否过期。
</details>

<details>
<summary>🔴 <b>连通性测试显示"未找到 (404)"？</b></summary>

> Endpoint 缺少 `/chat/completions` 路径后缀，或模型名称不正确。
</details>

<details>
<summary>🟡 <b>启动后显示"目录不存在"或"无聊天日志文件"？</b></summary>

> 请确认已安装 TruckersMP 并至少进入过一次联机服务器。日志目录位于 `文档\ETS2MP\logs\`。
</details>

<details>
<summary>🟡 <b>能看到日志文件但无法识别聊天内容？</b></summary>

> 如果 TruckersMP 版本较旧，日志格式可能不同。请更新 TMP 客户端到最新版本。
</details>

<details>
<summary>🟡 <b>看不到翻译窗口？</b></summary>

> 检查窗口是否在屏幕外 → 右键托盘图标选 "Show/Hide" 切换显示 → 尝试切换到标准窗口模式。
</details>

<details>
<summary>🟡 <b>悬浮模式下无法点击/拖拽窗口？</b></summary>

> 已开启鼠标穿透 → 通过系统托盘菜单先关闭点击穿透。
</details>

<details>
<summary>🟡 <b>按热键无法呼出输入栏？</b></summary>

> 在设置中点击热键输入框重新绑定。确认热键没被其他程序或游戏占用。
</details>

<details>
<summary>🟡 <b>如何把翻译好的文字发送到游戏？</b></summary>

> 翻译完成后按复制热键（默认 Ctrl+C）→ 游戏打开聊天框粘贴（Ctrl+V）→ 按发送热键（默认 Enter）。
</details>

<details>
<summary>🟢 <b>百度翻译和 LLM 翻译有什么区别？</b></summary>

> 百度翻译是专业神经机器翻译引擎，更准确更快，标准版每月 500 万字符免费。LLM 翻译更灵活但可能不够稳定。推荐使用 **LLM + 百度监督** 混合模式。
</details>

<details>
<summary>🟢 <b>如何申请百度翻译 API？</b></summary>

> 访问 [fanyi-api.baidu.com](https://fanyi-api.baidu.com/) 注册开发者 → 创建应用 → 获取 APP ID 和密钥 → 选择"标准版"免费使用。
</details>

<details>
<summary>🟢 <b>国内用户如何下载更新？</b></summary>

> v1.2.3 起内置 GitHub 镜像下载支持，自动通过 ghproxy.com 代理，国内直连无障碍。
</details>

---

## 📄 License · 许可证

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-10b981?style=for-the-badge" alt="MIT License">
</p>

<p align="center">
  本项目基于 <a href="LICENSE">MIT License</a> 开源 · 完全免费 · 可自由使用、修改和分发
</p>

<p align="center">
  
</p>
