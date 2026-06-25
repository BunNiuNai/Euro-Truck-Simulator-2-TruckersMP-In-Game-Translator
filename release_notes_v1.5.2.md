## 🔧 v1.5.2 — 窗口拖影修复

> **Window Ghosting Fix**

---

### 🐛 Bug 修复 (Bug Fix)

| 问题 | 修复 |
|:---|:---|
| **标准窗口模式拖影** | `overlay.py:_apply_mode()` 仅在悬浮(overlay)模式设置窗口透明度 `-alpha`，标准(standalone)模式设为全不透明 `1.0`。标准窗口不再走 Windows layered window 路径，DWM 正常合成，Text widget 局部重绘无残留 |
| **overlay→standalone 切换残留裁剪区域** | standalone 模式分支增加 `SetWindowRgn(hwnd, 0, True)`，清除 overlay 模式圆角裁剪的窗口区域 |

### 🔧 工程改进

| 改进 | 说明 |
|:---|:---|
| **exe 文件名含版本号** | `build_exe.py` 自动从 `config.py` 读取 `VERSION`，输出 `ETS2-TruckersMP翻译器-v1.5.2.exe`，方便识别版本 |

---

### 📦 下载

> `ETS2-TruckersMP翻译器-v1.5.2.exe` — 24MB, Windows 10/11, 无需 Python 环境

### 🔄 升级方式

- **exe 用户**: 下载新 exe 替换旧文件即可
- **源码用户**: `git pull && python main.py`
