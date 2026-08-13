# 翻译引擎改造设计：五层术语处理 + 对方发消息方式（保留多模型分流）

日期：2026-08-13

## Context

对比分析 GitHub 项目 [Seven-TMP/ets2-chat-translator](https://github.com/Seven-TMP/ets2-chat-translator) 后，发现对方翻译质量更强的核心原因不在于模型，而在于其**五层术语处理体系**（本地俚语字典 + 短语回退 + 结构化短语 + prompt 内嵌映射 + 后处理补译），以及**更规范的 LLM 消息构造方式**（system + user 结构、temperature=0、动态 max_tokens）。

同时发现本项目 v2.2.0 的"翻译提示简化"引入了回归：`receive_prompt.txt`（133 行 ETS2 术语）与 `send_prompt.txt` 已不再被实际调用，`translator.py` 的 `_call_provider` 与 `_call_api_legacy` 均使用硬编码单行 user 消息 `把以下文字翻译成简体中文，只输出译文：{text}`。

本改造目标是：放弃现有术语库方式，全面移植对方的五层术语处理与发消息方法，同时保留本项目的多模型轮转分流及全部现有特色能力。

## 决策记录（用户已确认）

| 决策点 | 结论 |
|---|---|
| 发送方向 | 只改用对方的 system+user 提示词结构（方向反转），**不套用**外语→中文俚语库 |
| 术语库形式 | 硬编码 Python 模块（不额外引入 JSON 配置文件） |
| 现有特色 | 混合语言智能拆分、批量翻译、LRU 缓存、同文本合并**全部保留** |
| ETS2 专有词汇 | 对方的俚语词典 **+ 保留**本项目术语库中的 ETS2 专有名词 |

## 架构

采用独立模块方案：新建 `chat_dictionary.py` 存放全部硬编码词典与纯函数处理逻辑，`translator.py` 只在入口/出口调用，保持 translator.py 不进一步膨胀。

```
monitor.py → raw_queue → translator.py（Translator 线程）
                          ├─ 入口：short_phrase_fallback() 本地字典拦截（命中→零 API 调用）
                          ├─ 未命中：混合语言拆分 → 轮转分流 → _call_provider
                          │            └─ system+user prompt（对方结构）
                          └─ 出口：fix_leftover_shorthand → preserve_mention_prefix
                                    → looks_untranslated 校验（失败回退下一家）
```

## 新模块 chat_dictionary.py

硬编码以下内容（全部来自对方源码，外加保留的 ETS2 词汇）：

1. **SLANG_TOKENS**（第1层）— 约 110 条俚语/缩写 → 中文，含 `pauseAfter` 标记
   - 缩写类：wtf/wdf/tf/wth→什么鬼、sry/sorry/soz/pardon→抱歉、ty/thx/thanks→谢谢、gg/wp→打得好、brb→马上回、afk→暂离、idk→我不知道…
   - 游戏类：rec/recording→已录屏、report/rep→举报、ban→封禁、kick→踢出、crash→撞车、ram/rammer→撞人玩家、lag/laggy→卡顿、dc/ds→Discord…
   - 脏话/嘲讽类：fk/fck/fuck/shit/stfu、ez→太简单了、noob→菜鸟、idiot→白痴…
   - 土耳其语：tamam→好的、neden→为什么、hayir→不、sa/as→你好、gel→过来…
2. **PHRASE_FALLBACK**（第2层）— 俄/德/土/系统消息/颜文字 → 中文精确匹配
   - 俄语：сам виноват→是你自己的错、кидай дс→发Discord、кину запись→我会发录像…
   - 德语：gute reise→一路顺风
   - 系统消息：cannot connect to server→无法连接到服务器、connection established→已连接到服务器…
   - 颜文字：o/→挥手、<3→爱心、: )→微笑、: (→难过
3. **STRUCTURED_PHRASES**（第3层）— rec ban→已录屏等封禁、report/ban/kick [名字]→举报/封禁/踢出[名字]
4. **PROMPT_MAPPING**（第4层）— prompt 内嵌 `Map sry=抱歉, ty/thx=谢谢, rec=已录屏, wtf=什么鬼`
5. **ETS2_TERMS**（保留层）— truck→卡车、trailer→挂车、cargo/load→货物、convoy→车队、garage→车库、ferry→渡轮、toll gate→收费站、speed limit→限速、overtake→超车、fuel/diesel→油/柴油、collision→碰撞、no collision/nc→无碰撞区、Scandinavia→斯堪的纳维亚、Calais→加来、Duisburg→杜伊斯堡 等

导出纯函数（可单测）：

- `short_phrase_fallback(text) -> str` — 本地字典回退，命中返回译文，未命中返回空串
- `looks_untranslated(input, output, target_lang) -> bool` — 判断 LLM 返回是否失败（输出为空/等于原文/目标为中文却无中文）
- `fix_leftover_shorthand(text) -> str` — 后处理补译 LLM 漏译的英文缩写
- `preserve_mention_prefix(input, output) -> str` — 保留 `@玩家名` 前缀
- `guess_source_language(text) -> str` — 多语言启发式检测（俄/希/土/德/波/捷/罗/西/葡/法/意）

## 接收方向改造 translator.py

**入口拦截**（在 `_flush_llm` 处理每条消息之前）：

```python
quick = short_phrase_fallback(text)
if quick:
    # 直接输出 quick，不进入 LLM
```

**`_call_provider` 的 prompt 改造**：

```python
system = (
    f"You translate TruckersMP/ETS2 multiplayer chat into {target}. "
    f"Output only the translation, no quotes, no explanations, no reasoning. "
    f"Any language/slang. Map sry=抱歉, ty/thx=谢谢, rec=已录屏, wtf=什么鬼. "
    f"Keep names, IDs, tags, URLs and emoji unchanged."
)
payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ],
    "temperature": 0,
    "max_tokens": max_output_tokens(text),  # 56 + len/4，clamp 64~160
}
# DeepSeek / MiMo：加 "thinking": {"type": "disabled"}
```

**出口后处理**（LLM 返回后）：

```python
out = fix_leftover_shorthand(out)
out = preserve_mention_prefix(text, out)
if looks_untranslated(text, out, target_lang):
    # 判定失败 → 回退下一家 provider（沿用现有 _call_api_internal 的轮转+熔断）
```

## 发送方向改造 translator.py

`_call_single_provider` / `_legacy_send_translate` 改用对方提示词结构（方向反转，无俚语库）：

```python
system = f"You translate into {目标语言}. Output only the translation, no quotes."
messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
temperature = 0, max_tokens = 动态，DeepSeek/MiMo thinking:disabled
```

## 保留项（不修改）

混合语言智能拆分（split_mixed_text / reassemble_mixed）、批量翻译（0.3s 窗口）、LRU 缓存（1000 条）、同文本合并、轮转分流、熔断冷却、DPAPI 配置、日志系统、监控、悬浮窗。

## 验收标准

1. `chat_dictionary.py` 单元测试覆盖：词典命中/未命中、短语回退、结构化短语、后处理补译、@mention 保留、untranslated 校验、源语言检测
2. 现有 7 个测试文件（test_*.py）全部通过，无回归
3. 端到端：`python main.py` 启动，模拟 "wtf are you doing" → 命中本地字典直接输出（不产生 API 调用）

## 涉及文件

- 新增：`chat_dictionary.py`
- 修改：`translator.py`
- 参考（只读，移植词典内容）：对方仓库 `src/translate_engine.cpp`（ChatTokenItems / ShortPhraseFallback / StructuredTruckersPhrase / FixProviderLeftoverShorthand / GuessSourceLanguage / LooksUntranslated）
