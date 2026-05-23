# 🚛 ETS2 Chat Translator · 欧卡聊天翻译器

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0.9-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?style=flat-square" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/downloads-GitHub%20Releases-9cf?style=flat-square" alt="Downloads">
</p>

<p align="center">
  <strong>Euro Truck Simulator 2 / TruckersMP 联机聊天实时翻译工具</strong>
</p>

<p align="center">
  自动将多国语言聊天消息翻译为简体中文，以半透明悬浮窗口显示在游戏中<br>
  支持中文输入 → 翻译为英文 → 一键发送到游戏聊天
</p>

<p align="center">
  <a href="https://github.com/BunNiuNai/ets2-translator/releases"><b>⬇️ 下载最新版</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-快速开始"><b>快速开始</b></a>
  &nbsp;&nbsp;·&nbsp;&nbsp;
  <a href="#-常见问题"><b>常见问题</b></a>
</p>

---

## 📖 目录

- [✨ 功能特性](#-功能特性)
- [🖥 系统要求](#-系统要求)
- [🚀 快速开始](#-快速开始)
- [⚙️ 配置说明](#️-配置说明)
- [📖 使用方式](#-使用方式)
- [🧠 推荐大模型](#-推荐大模型)
- [🔧 运行原理](#-运行原理)
- [📁 项目结构](#-项目结构)
- [📦 依赖](#-依赖)
- [📸 截图](#-截图)
- [❓ 常见问题](#-常见问题)
- [📄 许可证](#-许可证)

---

## ✨ 功能特性

| 功能 | 说明 |
|:---:|---|
| 🌐 **实时聊天翻译** | 监控 TruckersMP 聊天日志，批量翻译各语言消息到简体中文 |
| 📤 **反向翻译发送** | 输入中文 → 自动翻译为英文 → 热键发送到游戏聊天 |
| 👥 **全员翻译** | 所有玩家的消息均等翻译，不再区分自己与他人 |
| 📦 **批量翻译** | 0.8 秒窗口内收集多条消息，合并为一次 API 请求 |
| 💾 **LRU 缓存** | 200 条翻译缓存，相同消息直接命中，跳过 API 调用 |
| 🔀 **双翻译后端** | LLM API + 百度翻译 API，可独立使用或组合 |
| 🛡 **百度翻译监督** | 混合模式：LLM 先翻译 → 百度对比纠错 → 不一致时自动替换并红字提示 |
| 🔄 **一键自动更新** | 启动时自动检查 GitHub 新版本，右键菜单一键下载更新 |
| 🧩 **多种 LLM 支持** | 兼容 OpenAI API 格式（OpenAI、DeepSeek、Ollama、Groq 等） |
| 🔌 **连通性测试** | 设置中一键测试 API 连接，混合模式同时检测 LLM + 百度 |
| 🪟 **双窗口模式** | 标准窗口 / 无边框悬浮窗口，悬浮模式支持鼠标穿透和边缘拖拽缩放 |
| 📊 **API 用量统计** | 窗口底部实时显示翻译次数、缓存命中、跳过次数和节省百分比 |
| 📍 **窗口位置记忆** | 自动保存和恢复窗口位置与大小 |
| ✂️ **消息分割线** | 每条翻译消息下方显示白色横线分隔，便于快速区分 |
| ⌨️ **全局热键** | 可自定义组合键（如 Shift+Y）从游戏内呼出翻译器输入栏 |
| 📋 **系统托盘** | Win32 托盘图标，右键菜单快捷操作 |
| 💬 **聊天俚语翻译** | 内置网游缩写/俚语映射（lol→哈哈，brb→马上回来 等） |

---

## 🧠 推荐大模型

> 大模型推荐使用 **[硅基流动](https://siliconflow.cn/)**，模型选择 `Qwen/Qwen2.5-7B-Instruct`
>
> ✅ 永久免费 · 不限流 · 不限并发 · 国内直连
>
> 通义千问小模型，翻译快、准，个人用户随便用。

---

## 🖥 系统要求

- **操作系统**: Windows 10 / 11
- **Python**: 3.10+（exe 打包版无需 Python 环境）
- **游戏**: Euro Truck Simulator 2 + TruckersMP 联机插件

---

## 🚀 快速开始

### 方式一：Python 源码运行

```bash
# 1. 克隆仓库
git clone https://github.com/BunNiuNai/ets2-translator.git
cd ets2-translator

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行
python main.py
```

### 方式二：下载 exe 直接运行

从 [GitHub Releases](https://github.com/BunNiuNai/ets2-translator/releases) 下载最新的 `ETS2_Chat_Translator.exe`，双击运行即可，无需安装 Python 环境。

### 方式三：自行打包

```bash
python build_exe.py
# 输出: dist/ETS2_Chat_Translator.exe
```

---

## ⚙️ 配置说明

首次运行会自动弹出设置窗口，也可通过右键菜单 → **Settings / 设置** 打开。

填写 API 地址、密钥和模型后，点击 **Test / 测试连接** 验证配置是否可用，测试通过后点击 **Save / 保存**。

> 💡 配置会自动保存到 `文档\ETS2 Translator\config.json`，下次启动无需重新填写。每次启动时自动测试 API 连通性。

| 配置项 | 说明 | 示例 |
|:---|:---|---|
| 翻译后端 | LLM / 百度翻译 / LLM+百度监督 | `LLM+百度监督` |
| API Endpoint | LLM API 地址（OpenAI 兼容格式） | `https://api.openai.com/v1/chat/completions` |
| API Key | API 密钥 | `sk-xxxxxxxx` |
| Model | 模型名称 | `gpt-4o-mini` |
| 百度 APP ID | 百度翻译开放平台 APP ID | `20250101001234567` |
| 百度 Secret | 百度翻译开放平台密钥 | `xxxxxx` |
| 窗口透明度 | 0.1（几乎透明）~ 1.0（完全不透明） | `0.80` |
| 字体大小 | 翻译窗口字体大小 | `12` |
| 最大消息数 | 窗口内最多显示的消息条数 | `50` |
| 你的游戏ID | 在游戏中的玩家名称（可选，可自动检测） | `PlayerName` |
| 窗口模式 | 标准窗口 / 悬浮窗口 | `悬浮窗口` |
| 鼠标穿透 | 悬浮模式下鼠标点击穿透到游戏 | `否` |
| 游戏聊天键 | 游戏中打开聊天窗口的按键 | `y` |
| 复制热键 | 复制翻译结果到剪贴板的按键 | `ctrl+c` |
| 发送热键 | 确认消息已发送的按键（游戏内发送键） | `enter` |
| 呼出输入框热键 | 全局热键，从游戏中呼出翻译器输入栏 | `shift+y` |

### 热键设置

点击设置中的热键标签 → 标签变为 **"按下组合键..."** → 直接按下键盘组合键（如 Shift+Z）→ 自动识别并保存。

> ⚠️ **注意：绑定按键要锁定大写！**

---

## 📖 使用方式

1. 启动 ETS2 并进入 TruckersMP 联机模式
2. 运行翻译器，窗口会以悬浮或标准模式显示
3. **查看翻译**：其他玩家的消息会自动翻译并显示在窗口中
4. **发送消息**：
   - 按全局热键（默认 `Shift+Y`）呼出输入栏
   - 输入中文 → 回车 → 自动翻译为英文
   - 翻译结果显示在输入框 → 按复制热键复制到剪贴板
   - 在游戏中手动粘贴到聊天框 → 按发送热键确认发送
5. 系统托盘图标右键可进行快捷操作
6. 右键点击翻译窗口可打开设置菜单

---

## 🔧 运行原理

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      ETS2 / TruckersMP                           │
│  游戏内聊天 ──→ 写入日志文件 chat_YYYY-MM-DD_log.txt               │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼ (文件增量读取)
┌─────────────────────────────────────────────────────────────────┐
│  monitor.py — 聊天日志监控                                        │
│  · 通过注册表获取 Documents 路径，定位日志目录                     │
│  · 匹配日志文件: chat_YYYY_MM_DD_log.txt                          │
│  · 每 0.5s 轮询文件大小变化，增量读取新行                          │
│  · 正则解析: [Channel] [HH:MM:SS] PlayerName (TMP_ID): Message   │
│  · 所有玩家消息均等处理，统一进入翻译队列                           │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼ (raw_queue)
┌─────────────────────────────────────────────────────────────────┐
│  translator.py — 批量翻译引擎                                      │
│  · LRU 缓存 (200条)，相同原文直接命中                               │
│  · 批量模式: 0.8s 窗口收集消息，合并为一次 API 请求                 │
│  · 跳过自己发送的消息                                               │
│  · 跳过已是中文的消息                                               │
│  · LLM / 百度 / LLM+百度监督 三种后端可选                           │
│  · translate_to_english(): 反向翻译（中文→英文）                    │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼ (display_queue)
┌─────────────────────────────────────────────────────────────────┐
│  overlay.py — 翻译显示窗口                                         │
│  · 每 250ms 轮询 display_queue，空闲时合并刷新                      │
│  · 双模式: 标准窗口 / 无边框悬浮窗                                   │
│  · 悬浮模式: Win32 API 实现鼠标穿透、拖拽、边缘缩放                  │
│  · 底部输入栏: 热键呼出 → 抢焦点 → 可直接输入                        │
│  · 发送流程: 回车 → 翻译 → 结果显示 → 手动热键发送                 │
│  · API 用量统计栏                                                  │
│  · 窗口位置自动保存和恢复                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 消息生命周期

```
1. 玩家在游戏内发送聊天
       │
2. TruckersMP 写入 chat_YYYY_MM_DD_log.txt
       │
3. ChatMonitor 检测到文件变化，增量读取新行
       │
4. 正则解析 → ChatMessage，所有消息均等发送到翻译队列
       │
5. 放入 raw_queue
       │
6. Translator 取出，检查 LRU 缓存
       │   命中缓存 → 直接返回
       │   未命中 → 加入批量队列
       │
7. 批量窗口到期 → 合并发送一次 API 请求
       │
8. 翻译结果拆分后分别放入 display_queue
       │
9. OverlayWindow 每 250ms 轮询队列（空闲合并刷新）
       │
10. 增量更新 Text 组件，更新统计栏，自动滚到底部
```

### 发送消息流程

```
1. 用户在游戏中按全局热键 (如 Shift+Y) 呼出输入栏
   │   翻译器窗口置顶，AttachThreadInput 抢焦点
   │   用户可直接输入中文
       │
2. 输入中文消息，按回车
   │   输入框禁用，显示"翻译中..."
   │   后台调用翻译引擎 中文 → 英文
       │
3. 翻译完成 → 翻译结果显示在输入框并自动选中
   │   显示"翻译完成 | 用热键手动发送"
   │   启动手动热键轮询器
       │
4. 用户按复制热键（默认 Ctrl+C）
   │   系统自然处理复制，翻译文字进入剪贴板
   │   翻译器检测到按键 → 显示"已复制到剪贴板"
       │
5. 用户在游戏中打开聊天框，粘贴译文
   │   翻译器不参与此步骤
       │
6. 用户按发送热键（默认 Enter）发送消息
   │   翻译器检测到按键 → 停止轮询器
   │   已发送消息显示在翻译窗口（(Sent) 标签）
   │   输入框清空，恢复初始状态
```

---

## 📁 项目结构

```
ets2-translator/
├── main.py              # 入口、主控、设置对话框
├── config.py            # 配置模型、JSON 读写、注册表获取 Documents 路径
├── monitor.py           # 聊天日志监控（增量轮询、正则解析）
├── translator.py        # 翻译引擎（LLM API / 百度 API / 混合模式、LRU 缓存）
├── overlay.py           # 显示窗口（Tkinter + Win32 API、输入栏、全局热键）
├── input_sender.py      # 键盘模拟发送（SendInput API）
├── tray_icon.py         # 系统托盘图标（纯 ctypes + Win32 API）
├── update.py            # 自动更新（GitHub 版本检查、下载、替换重启）
├── build_exe.py         # PyInstaller 打包脚本
├── requirements.txt     # Python 依赖
├── icon.ico             # 程序图标
├── README.md
└── dist/                # 构建输出
    └── ETS2_Chat_Translator.exe
```

---

## 📦 依赖

| 包 | 用途 |
|:---:|---|
| `httpx` | HTTP 客户端，调用 LLM API |

Tkinter 为 Python 标准库，系统托盘和键盘模拟均使用纯 ctypes + Win32 API，无需 pystray、Pillow 等第三方库。

---

## 📸 截图

> 📌 *截图待补充 — 欢迎提交 PR！*

<!--
![翻译窗口](screenshots/overlay.png)
![设置面板](screenshots/settings.png)
![托盘菜单](screenshots/tray.png)
-->

---

## ❓ 常见问题

<details>
<summary><b>翻译结果显示 "[网络错误] 无法连接到 API 服务器"？</b></summary>
请检查 API Endpoint 地址是否正确，网络是否能访问该地址。
</details>

<details>
<summary><b>翻译结果显示 "[认证失败] API 密钥无效"？</b></summary>
请检查 API Key 是否正确填写，密钥是否过期。
</details>

<details>
<summary><b>连通性测试显示 "API 地址不存在 (404)"？</b></summary>
请检查 API Endpoint 是否包含完整路径（如 <code>https://api.deepseek.com/v1/chat/completions</code>），以及模型名称是否正确。
</details>

<details>
<summary><b>启动后显示"目录不存在"或"目录存在但无聊天日志文件"？</b></summary>
请确认已安装 TruckersMP 并至少进入过一次联机服务器。日志目录位于 <code>文档\ETS2MP\logs\</code>，首次进入游戏后会自动创建。
</details>

<details>
<summary><b>能看到日志文件但无法识别聊天内容？</b></summary>
如果 TruckersMP 版本较旧，日志格式可能不同。请更新 TruckersMP 客户端到最新版本。
</details>

<details>
<summary><b>为什么看不到翻译窗口？</b></summary>
检查窗口是否在屏幕外；右键系统托盘图标选择 "Show/Hide" 切换显示；尝试切换到标准窗口模式。
</details>

<details>
<summary><b>悬浮模式下无法点击/拖拽窗口？</b></summary>
如果开启了鼠标穿透，窗口不接受鼠标点击。请通过系统托盘菜单关闭点击穿透后再操作。
</details>

<details>
<summary><b>按热键无法呼出输入栏？</b></summary>
请确认热键设置正确（在设置中点击热键标签后直接按组合键重新设置）。注意全局热键可能被其他程序或游戏拦截。
</details>

<details>
<summary><b>热键按下后游戏聊天框也打开了？</b></summary>
翻译器会通过 AttachThreadInput + SetForegroundWindow 抢占焦点，输入焦点会从游戏转移到翻译器。如果仍有问题，尝试更换热键组合。
</details>

<details>
<summary><b>翻译完成后如何发送到游戏？</b></summary>
翻译结果显示后，按复制热键（默认 Ctrl+C）将文本复制到剪贴板，然后在游戏中手动打开聊天框粘贴（Ctrl+V），按发送热键（默认 Enter）发送。
</details>

<details>
<summary><b>发送消息时提示"翻译失败"？</b></summary>
请检查 API 配置是否正确，确保 API 可以正常访问。
</details>

<details>
<summary><b>百度翻译和 LLM 翻译有什么区别？</b></summary>
百度翻译是专业神经机器翻译引擎，翻译更准确、速度更快，标准版每月 500 万字符免费。LLM 翻译更灵活但可能不够稳定。推荐使用 <b>LLM + 百度监督</b> 混合模式。
</details>

<details>
<summary><b>如何申请百度翻译 API？</b></summary>
访问 <a href="https://fanyi-api.baidu.com/">fanyi-api.baidu.com</a> 注册成为开发者，创建应用获取 APP ID 和密钥。选择"标准版"即可免费使用。
</details>

<details>
<summary><b>如何更新到新版本？</b></summary>
启动时自动检查更新，有新版会在窗口提示。右键菜单 → <b>Check Updates / 检查更新</b> 即可自动下载并安装更新。
</details>

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源，完全免费，可放心使用。

<p align="center">
  <sub>Made with ❤️ for the ETS2 TruckersMP community</sub>
</p>
