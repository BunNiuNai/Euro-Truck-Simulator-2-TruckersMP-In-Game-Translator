# 🚛 ETS2 TruckersMP Chat Translator · 欧卡联机聊天翻译器

<p align="center">
  <img src="https://img.shields.io/badge/version-v2.2.0-4494FC?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-10b981?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?style=for-the-badge&logo=windows" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python" alt="Python">
</p>

<p align="center">
  <img src="https://img.shields.io/github/downloads/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator/total?style=flat-square&color=3b82f6&label=总下载" alt="Downloads">
  <img src="https://img.shields.io/github/stars/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator?style=flat-square&color=f59e0b" alt="Stars">
  <img src="https://img.shields.io/github/last-commit/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator?style=flat-square&color=64748b" alt="Last Commit">
  <img src="https://img.shields.io/github/repo-size/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator?style=flat-square&color=8b5cf6" alt="Repo Size">
</p>

<p align="center">
  <strong>🌍 实时多语言聊天翻译 · 毛玻璃悬浮窗 · 一键发送 · 20+ LLM 预设 · exe 免安装</strong><br>
  <sub>Real-time in-game chat translator for Euro Truck Simulator 2 / TruckersMP</sub>
</p>

<p align="center">
  <a href="https://github.com/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator/releases/latest">
    <img src="https://img.shields.io/badge/⬇️%20下载最新版-Download%20Latest-4494FC?style=for-the-badge&logo=github" alt="Download">
  </a>
</p>

<p align="center">
  <a href="#-quick-start--快速开始">🚀 快速开始</a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-features--功能特性">✨ 功能特性</a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-推荐大模型">🧠 推荐模型</a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-faq--常见问题">❓ 常见问题</a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-changelog--更新日志">📋 更新日志</a>
</p>

---

> [!TIP]
> 🚛 在 ETS2 TruckersMP 联机中，自动将各国语言聊天实时翻译为简体中文，以现代毛玻璃悬浮窗显示。支持中文打字 → 自动翻译为英文 → 一键发送到游戏聊天。
>
> 🎨 **v2.2.0**：Win11 Mica / Win10 Acrylic 毛玻璃效果 · 多模型轮转负载均衡 · 统一日志系统 · 代码质量加固
>
> 💯 **完全免费 · 开源 · 无需安装 Python**

---

## 📖 目录

- [✨ 功能特性](#-features--功能特性)
  - [🌐 核心翻译](#-核心翻译)
  - [🧠 智能翻译引擎](#-智能翻译引擎)
  - [🪟 窗口与交互](#-窗口与交互)
  - [📋 日志与诊断](#-日志与诊断)
  - [🔧 其他特性](#-其他特性)
- [📋 更新日志](#-changelog--更新日志)
- [🧠 推荐大模型](#-推荐大模型)
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
| 🔄 | **多模型轮转负载均衡** | 多个 LLM Provider 按轮转顺序分配翻译任务，避免排队等待 |
| 📦 | **20+ Provider 预设** | 内置国内外主流 LLM 供应商模板，一键填入地址和模型 |
| 📥 | **模型列表拉取** | 从 API 端点自动获取可用模型，无需手动查模型名 |
| 🛡️ | **Provider 熔断回退** | 连续失败自动冷却，成功恢复；全部失败串行重试 |
| 📦 | **批量翻译** | 0.3 秒窗口收集多条消息，合并为一次 API 请求 |
| 💾 | **LRU 缓存 1000 条** | 重复消息直接命中缓存，零延迟零消耗 |
| 🌐 | **混合语言智能拆分** | 中文片段保留不译，只翻译非中文部分，适配游戏混合聊天 |
| 📊 | **同文本请求合并** | 相同原文并发到达时自动合并为一次 API 调用 |
| 🔐 | **DPAPI 加密存储** | API Key 使用 Windows 系统级加密，配置文件不暴露明文 |
| 🎯 | **发送目标语言** | 支持 10 种目标语言：中/英/日/韩/德/法/西/俄/葡/意 |

### 🪟 窗口与交互

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 🪟 | **毛玻璃悬浮窗** | Win11 Mica / Win10 Acrylic 亚克力模糊效果，纯黑透明底色 + 1px 蓝色描边 |
| 🎨 | **三层蓝色配色** | `#4494FC` 主色调 / `#60A8FF` 描边线 / `#70B8FF` 高亮文字，冷色调科技风格 |
| 📐 | **四段式纵向布局** | 蓝色 accent 线 → 标题栏（版本+服务器）→ 消息区 → 输入框 → 统计栏 |
| ⌨️ | **系统级全局热键** | `RegisterHotKey` 系统热键，不会被游戏拦截 |
| 📋 | **系统托盘图标** | 右键托盘菜单：显示/隐藏、切换模式、鼠标穿透、设置、退出 |
| 🕐 | **北京时间显示** | 标题栏右侧实时显示北京时间 |
| 🏷️ | **服务器自动识别** | 自动解析聊天日志中的 `Connecting to X server...` 并更新标题栏 |
| ⏱️ | **消息时间戳** | 每条消息右侧对齐显示 `HH:MM:SS` 时间 |
| 📝 | **输入框常驻** | 消息区与统计栏之间直接显示，随时输入 |
| ✨ | **译文金色显示** | 翻译结果在悬浮窗中以金色高亮展示 |

### 📋 日志与诊断

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 📋 | **统一日志系统** | 翻译日志和消息日志合二为一，格式：`时间 - 厂商-模型名 - 原文 - 译文` |
| 📂 | **自动写入文件** | 日志保存到 `文档\ETS2 Translator\logs\`，自动轮转 |
| 🔍 | **一键测试全部** | 测试所有 Provider 的连通性 |

### 🔧 其他特性

| 🏷️ | 功能 | 说明 |
|:---:|---|---|
| 🔥 | **配置热重载** | 修改配置文件 3 秒自动生效，无需重启 |
| 💬 | **游戏术语库** | 内置 130+ 行 ETS2 专用术语 + 100+ 条网游俚语 |
| ✂️ | **消息分割线** | 每条翻译消息下方分隔线，快速区分 |
| 🚫 | **聊天去重** | 同一条消息（玩家+内容+时间戳）不重复显示 |

---

## 📋 Changelog · 更新日志

### 🔥 v2.2.0 — 热修复版本（代码质量加固）

- **🔧 移除百度翻译** — 删除全部百度 API 代码、Provider 预设、配置字段和 UI，翻译引擎回归纯 LLM 轮转
- **🛡️ 50+ 代码质量修复** — DPAPI 加密安全、线程安全、剪贴板恢复、日志轮转、窗口毛玻璃回退
- **📝 翻译提示简化** — 接收翻译从 133 行 system prompt 简化为单条 user 消息，与发送翻译风格一致

### 🚀 v2.1.0 — 翻译架构重构

- **🔄 多模型轮转负载均衡** — 多个 Provider 按轮转顺序分配翻译任务，避免排队等待，单 Provider 行为不变
- **📋 统一日志系统** — 翻译日志和消息日志合二为一，格式统一，修复删除日志按钮无效的 Bug
- **🎯 发送目标语言** — 支持 10 种目标语言，简洁指令格式兼容 Hunyuan-MT-7B、Qwen2.5-7B、Qwen3-8B 等小模型
- **✨ 译文金色显示** — 翻译结果在悬浮窗中以金色高亮展示
- **🔧 多项修复** — Test 按钮无反应、删除日志崩溃、设置保存丢失配置、Translator 未初始化属性等

<details>
<summary><b>📦 历史版本 — 点击展开</b></summary>

### 🎨 v2.0.0 — 现代毛玻璃 UI 全面重构

- **🪟 全新毛玻璃悬浮窗** — Win11 Mica / Win10 Acrylic 自动适配，纯黑无色透明背景 + 1px 蓝色描边
- **🎨 三层蓝色配色** — `#4494FC` 主色调 / `#60A8FF` 描边线 / `#70B8FF` 高亮文字
- **📐 四段式纵向布局** — 蓝色 accent 线 → 标题栏 → 消息区 → 输入框 → 统计栏
- **🏷️ 服务器自动识别** — 标题栏实时显示当前连接的服务器名称
- **⏱️ 消息时间戳** — 每条消息右侧对齐显示 `HH:MM:SS`
- **📝 输入框常驻** — 消息区下方直接输入，无需按热键呼出
- **🔧 系统消息翻译修复** — TMP 系统通知正确翻译为中文
- **🧪 72 个单元测试** — 覆盖核心模块

### 🚀 v1.8.0 — Provider 预设系统 & 混合语言智能翻译

- **📦 Provider 预设系统** — 内置 20+ 国内外 LLM 供应商预设，点击自动填入 API 地址和推荐模型
- **📥 模型列表拉取** — 一键从 API 端点获取可用模型列表
- **🌐 混合语言智能翻译** — 消息中夹杂中文的部分原样保留，只翻译非中文片段
- **🔍 连通性测试** — Provider 编辑区新增实时 API 延迟检测
- **🛠️ 日志删除修复** — 修复翻译器日志无法通过系统按钮删除的问题

### 📤 v1.6.0 / v1.7.0

- 广告消息自动定时发送、Provider 权重配置、API 格式支持（OpenAI + Anthropic）

### 🔧 v1.5.2 — 窗口渲染修复

- 标准窗口模式拖影问题修复，不再走 Windows layered window
- exe 文件名含版本号，方便识别

### 📤 v1.5.1 / v1.5.0 — 自动发送 + 日志管理

- 中文输入 → 自动翻译 → 自动发送到游戏，全流程自动化
- 翻译器日志 + 消息日志分拆管理，支持文件夹打开/删除/刷新

### 🛡️ v1.4.0 — 21 项稳定性修复

- 线程安全、DPAPI 加密、崩溃恢复、内存泄漏、竞态条件全面修复
- 启动时跳过历史消息，仅增量读取新消息

### 🌐 v1.3.0 — 多 Provider 并行竞速

- 配置多个大模型 API，翻译时并行竞速，最快的结果立即返回
- Provider 熔断冷却、同文本并发合并、配置热重载
- 热键升级为 `RegisterHotKey` 系统级热键
- TMP 系统消息翻译 + VS Code 深灰主题 + 窗口圆角 + 北京时间

</details>

---

## 🧠 推荐大模型

> [!NOTE]
> 任意兼容 OpenAI API 格式的服务均可使用，填写地址、密钥和模型名即可。

| 🏢 提供商 | 🤖 推荐模型 | 💰 价格 | 📝 备注 |
|:---|:---|:---|:---|
| 🏔️ [SiliconFlow 硅基流动](https://siliconflow.cn/) | `Qwen/Qwen3-8B` | 🆓 免费额度 | 国内直连，不限并发 |
| 🐋 [DeepSeek](https://platform.deepseek.com/) | `deepseek-chat` | ¥1/1M tokens | 翻译质量极佳 |
| 🤖 [OpenAI](https://platform.openai.com/) | `gpt-4o-mini` | $0.15/1M tokens | 便宜可靠 |
| ⚡ [Groq](https://groq.com/) | `llama-3.3-70b` | 🆓 免费额度 | 推理速度极快 |
| 🏠 [Ollama](https://ollama.com/) | `qwen3:8b` | 🆓 本地免费 | 无需网络，隐私安全 |

> [!TIP]
> 🔥 **国内用户推荐**：硅基流动 + Qwen3-8B，免费额度、国内直连、速度快。
>
> 🌍 **海外用户推荐**：OpenAI `gpt-4o-mini` 或 DeepSeek，便宜且翻译质量高。

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

从 [📥 GitHub Releases](https://github.com/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator/releases/latest) 下载最新 `ETS2-TruckersMP翻译器-v2.2.0.exe`，双击运行即可。

> ✅ 无需安装 Python · 无需配置环境 · 开箱即用

### 方式二：🐍 Python 源码运行

```bash
# 1️⃣ 克隆仓库
git clone https://github.com/BunNiuNai/Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator.git
cd Euro-Truck-Simulator-2-TruckersMP-In-Game-Translator

# 2️⃣ 安装依赖
pip install -r requirements.txt

# 3️⃣ 运行
python main.py
```

### 方式三：🔨 自行打包

```bash
python build_exe.py
# 输出 → dist/ETS2-TruckersMP翻译器-v2.2.0.exe
```

---

## ⚙️ Configuration · 配置说明

> 🔰 首次运行自动弹出设置窗口，也可通过系统托盘右键 → **Settings / 设置** 打开。

### 🌐 Provider 配置（多 LLM 支持）

> 💡 点击 **📦 预设** 按钮，从 20+ 内置供应商中一键选择，自动填入 API 地址和推荐模型，只需填写 API Key。

| ⚙️ 配置项 | 📝 说明 | 💡 示例 |
|:---|:---|:---|
| 🏷️ **Label** | Provider 名称 | `DeepSeek` |
| 🔗 **Endpoint** | API 地址（**必须包含完整路径**） | `https://api.deepseek.com/v1/chat/completions` |
| 🔑 **API Key** | API 密钥 | `sk-xxxxxxxx` |
| 🤖 **Model** | 模型名称 | `deepseek-chat` |
| ✅ **Enabled** | 启用/禁用此 Provider | ☑ |

> [!WARNING]
> Endpoint 必须是完整 URL（含 `/chat/completions`），否则会返回 404。

### ⚙️ 其他配置

| ⚙️ 配置项 | 📝 说明 | 💡 示例 |
|:---|:---|:---|
| 🌐 **目标语言** | 翻译目标语言 | `简体中文` |
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

> [!WARNING]
> 绑定热键前请关闭 Caps Lock 大写锁定！

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
│  · 多 Provider 轮转负载均衡 + 熔断回退                          │
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
├── 📡 monitor.py           # TMP 聊天日志监控（增量轮询、正则解析、服务器识别）
├── 🧠 translator.py        # 翻译引擎（多Provider轮转、熔断、缓存、批量、混合语言拆分）
├── 🪟 overlay.py           # 显示窗口（毛玻璃悬浮窗、grid 布局、Win32 API、输入栏、热键）
├── 🪟 acrylic_helper.py    # Win32 亚克力/云母毛玻璃效果（Win11 Mica + Win10 Acrylic）
├── ⌨️ hotkey_manager.py     # 系统热键管理（RegisterHotKey + 消息窗口）
├── 📨 input_sender.py      # 键盘模拟（SendInput API、剪贴板）
├── 📋 tray_icon.py         # 系统托盘（纯 ctypes + Win32 API）
├── 🎨 settings_ui.py       # 设置 UI（Provider 预设选择、模型拉取、连通测试）
├── 📦 provider_presets.py  # 内置 20+ LLM 供应商预设模板
├── 📥 model_fetcher.py     # 模型列表拉取（/v1/models 端点探测）
├── 🏗️ build_exe.py          # PyInstaller 打包脚本
├── 📊 win32_constants.py   # Win32 常量/结构体共享模块
├── 💬 message_display.py   # 消息渲染引擎
├── 📦 message_types.py     # 数据类（DisplayMessage / TranslationStats）
├── 📝 logger.py            # 日志模块（文件轮转 + 内存缓冲）
├── 📄 requirements.txt     # Python 依赖
├── 🎨 icon.ico             # 程序图标
└── 📦 dist/                # 构建输出
    └── ETS2-TruckersMP翻译器-v2.2.0.exe
```

---

## ❓ FAQ · 常见问题

<details>
<summary>🔴 <b>翻译显示"网络错误"无法连接到 API 服务器？</b></summary>

> 检查 API Endpoint 地址是否正确。**必须包含完整路径**，如 `https://api.deepseek.com/v1/chat/completions`，只填 `https://api.deepseek.com/v1` 会导致 404。
</details>

<details>
<summary>🔴 <b>翻译显示"认证失败"API 密钥无效？</b></summary>

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

> 翻译完成后按复制热键（默认 `Ctrl+C`）→ 游戏打开聊天框粘贴（`Ctrl+V`）→ 按发送热键（默认 `Enter`）。
</details>

<details>
<summary>🆕 <b>如何使用预设功能快速添加 Provider？</b></summary>

> 设置 → API 配置 → 点击 **📦 预设** 按钮 → 搜索/选择供应商 → 自动填入地址和模型 → 只需填写 API Key → 保存。
</details>

<details>
<summary>🆕 <b>混合语言消息翻译不准怎么办？</b></summary>

> v1.8.0+ 已支持混合语言智能拆分：中文部分自动保留不动，只翻译非中文片段。例如 "你好 where are you" → "你好 你在哪里"。
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
  <sub>Made with ❤️ for the ETS2 TruckersMP community</sub>
</p>
