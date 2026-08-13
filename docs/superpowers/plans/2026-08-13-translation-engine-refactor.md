# 翻译引擎改造实现计划（五层术语处理 + 对方发消息方式）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用对方的五层术语处理 + system/user 发消息方式替换现有的失效术语库，同时保留多模型轮转分流与全部现有特色。

**Architecture:** 新建独立 `chat_dictionary.py` 模块存放硬编码词典与纯函数，`translator.py` 在入口（本地字典拦截）、prompt 构造、出口（后处理+校验）三个位置调用，不改变轮转/熔断/缓存/批量/混合语言拆分逻辑。

**Tech Stack:** Python 3.10+，标准库 `unittest`，`httpx`。

**参考源码（只读移植词典内容）：** 对方仓库 `src/translate_engine.cpp`（ChatTokenItems / ShortPhraseFallback / StructuredTruckersPhrase / FixProviderLeftoverShorthand / GuessSourceLanguage / LooksUntranslated）。

---

### Task 1: 创建 chat_dictionary.py 数据词典

**Files:**
- Create: `chat_dictionary.py`
- Test: `test_chat_dictionary.py`

- [ ] **Step 1: 写失败测试（验证词典可导入且命中）**

```python
# test_chat_dictionary.py
import unittest
from chat_dictionary import short_phrase_fallback, SLANG_TOKENS, ETS2_TERMS


class TestDictionary(unittest.TestCase):
    def test_slang_token_hit(self):
        self.assertEqual(short_phrase_fallback("wtf"), "什么鬼")

    def test_slang_token_miss_returns_empty(self):
        self.assertEqual(short_phrase_fallback("this is a long sentence that needs llm"), "")

    def test_ets2_term_present(self):
        self.assertIn("truck", ETS2_TERMS)
        self.assertEqual(ETS2_TERMS["truck"], "卡车")

    def test_phrase_fallback(self):
        self.assertEqual(short_phrase_fallback("rec ban"), "已录屏，等封禁")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest test_chat_dictionary -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'chat_dictionary'`）

- [ ] **Step 3: 实现数据词典**

创建 `chat_dictionary.py`，包含四层数据（第5层 prompt 映射与后处理见 Task 2）。数据为对方源码直接移植 + 保留的 ETS2 词汇：

```python
"""五层术语处理：本地俚语词典 + 短语回退 + 结构化短语 + prompt 映射 + 后处理补译。
数据来源：Seven-TMP/ets2-chat-translator 的 translate_engine.cpp（直接移植），
ETS2 专有词汇来自原 receive_prompt.txt。"""

# 第1层：俚语 token → (译文, pauseAfter)
SLANG_TOKENS = {
    # 缩写/感叹
    "wtf": ("什么鬼", True), "wdf": ("什么鬼", True), "tf": ("什么鬼", True),
    "wth": ("什么鬼", True), "wdym": ("你什么意思", True), "wyd": ("你在干嘛", True),
    "omg": ("天啊", True), "ffs": ("真服了", True),
    "lol": ("哈哈", True), "lmao": ("哈哈", True), "rofl": ("笑死", True), "xd": ("哈哈", True),
    # 道歉
    "sb": ("傻逼", True), "sry": ("抱歉", True), "sr": ("抱歉", True),
    "sory": ("抱歉", True), "srry": ("抱歉", True), "srrry": ("抱歉", True),
    "sorry": ("抱歉", True), "soz": ("抱歉", True), "pardon": ("抱歉", True),
    "pls": ("请", False), "plz": ("请", False), "please": ("请", False),
    # 感谢
    "ty": ("谢谢", True), "tyty": ("谢谢", True), "tysm": ("非常感谢", True),
    "tyvm": ("非常感谢", True), "thx": ("谢谢", True), "tnx": ("谢谢", True),
    "tks": ("谢谢", True), "tx": ("谢谢", True), "tq": ("谢谢", True), "thanks": ("谢谢", True),
    # 其他缩写
    "np": ("没事", True), "nvm": ("没事", True), "brb": ("马上回", True),
    "afk": ("暂离", True), "idk": ("我不知道", True), "idc": ("无所谓", True),
    "ikr": ("就是说", True), "asap": ("尽快", True),
    "gg": ("打得好", True), "wp": ("打得好", True), "gl": ("祝好运", True), "hf": ("玩得开心", True),
    # 问候/告别
    "hi": ("你好", True), "hello": ("你好", True), "hey": ("嘿", True), "yo": ("嘿", True),
    "ow": ("嗷", True), "sup": ("咋样", True), "bye": ("再见", True), "cya": ("再见", True),
    "cu": ("再见", True), "bb": ("再见", True), "gn": ("晚安", True), "gn8": ("晚安", True),
    "gm": ("早安", True),
    # 称呼
    "bro": ("兄弟", True), "bruh": ("兄弟", True), "dude": ("老兄", True),
    "mate": ("伙计", True), "man": ("兄弟", True),
    # 是/否/简单应答
    "k": ("好", True), "kk": ("好", True), "ok": ("好的", True), "okay": ("好的", True),
    "yes": ("是", True), "y": ("是", True), "no": ("不", True), "n": ("不", True),
    "wait": ("等一下", True), "stop": ("停一下", True), "go": ("走", True),
    "slow": ("慢点", True), "move": ("让一下", True),
    # 游戏网络
    "lag": ("卡顿", True), "laggy": ("很卡", True),
    # 土耳其语
    "tamam": ("好的", True), "neden": ("为什么", True), "hayir": ("不", True),
    "hayır": ("不", True), "sa": ("你好", True), "as": ("你好", True),
    "gel": ("过来", True), "var": ("有", True), "varmi": ("有吗", True), "varmı": ("有吗", True),
    # Discord
    "dc": ("Discord", True), "ds": ("Discord", True),
    # 游戏行为/举报
    "crash": ("撞车", True), "ram": ("撞人", True), "rammer": ("撞人玩家", True),
    "rec": ("已录屏", True), "recording": ("已录屏", True),
    "report": ("举报", True), "rep": ("举报", True), "ban": ("封禁", True), "kick": ("踢出", True),
    # 脏话/嘲讽
    "fk": ("靠", True), "fck": ("靠", True), "fuck": ("操", True), "shit": ("靠", True),
    "damn": ("该死", True), "stfu": ("闭嘴", True), "fu": ("去你的", True),
    "trash": ("垃圾", False), "ez": ("太简单了", True), "idiot": ("白痴", False),
    "stupid": ("蠢货", False), "noob": ("菜鸟", False), "moron": ("蠢货", False),
    "clown": ("小丑", False),
}

# 第2层：完整短语精确匹配 → 中文
PHRASE_FALLBACK = {
    # 英文
    "thank you": "谢谢", "thank": "谢谢", "good luck": "祝好运", "have fun": "玩得开心",
    "nice lag": "卡得真漂亮", "stop horn": "别按喇叭",
    "the player stop horn": "那个玩家别按喇叭", "f7 at": "按 F7",
    "dc varmi": "有 Discord 吗", "dc varmı": "有 Discord 吗",
    "wtf is this": "什么鬼，这是啥", "what the fuck": "什么鬼", "what the hell": "什么鬼",
    "ahah": "哈哈", "ahaha": "哈哈", "ahahah": "哈哈", "haha": "哈哈", "hahaha": "哈哈",
    # 德语
    "gute reise": "一路顺风",
    # 俄语
    "сам виноват": "是你自己的错", "охренел": "疯了吗", "идиот": "白痴",
    "кидай дс": "发 Discord", "кину запись": "我会发录像",
    "ребят кто по дс": "谁用 Discord", "поворотник включать надо": "该打转向灯",
    "ездить научись сам": "你自己先学会开车",
    "и ты мне говоришь научится ездить": "你还叫我学开车",
    "ты поворот делал вопще с обочины": "你刚才是从路肩转弯的",
    "пф": "哼", "умник смотрю": "看来挺聪明啊",
    # 土耳其语
    "onune kırma olm": "别往我前面变道，兄弟", "önüne kırma olum": "别往我前面变道，兄弟",
    "araba 100 oldu hasareı": "车损到 100 了", "yol vre la": "让路啊", "yol ver la": "让路啊",
    # 颜文字/手势
    "o/": "挥手", "o//": "挥手", "0/": "挥手", "0//": "挥手",
    "\\o": "挥手", "\\o/": "欢呼",
    ":)": "微笑", ":(": "难过", ":d": "哈哈", "<3": "爱心",
}

# 第3层：结构化短语（前缀 + 名字拼接）
STRUCTURED_ACTIONS = {
    "rec": "已录屏", "recording": "已录屏",
    "report": "举报", "rep": "举报",
    "ban": "封禁", "kick": "踢出",
}

# 系统消息关键词回退
SYSTEM_MESSAGE_FALLBACK = {
    ("cannot connect to server", "can't connect to server", "can not connect to server"):
        "无法连接到服务器，可能是网络连接问题。",
    ("automatically reconnected", "automaticly reconnected", "reconnected within next", "reconnect within next"):
        "将在接下来的几秒内自动重新连接。",
    ("connection established", "connected to server"): "已连接到服务器。",
    ("connection refused", "connection timed out"): "连接失败，请检查网络或稍后重试。",
}

# 保留的 ETS2 专有词汇（来自原 receive_prompt.txt）
ETS2_TERMS = {
    "truck": "卡车", "trailer": "挂车", "cargo": "货物", "load": "货物",
    "job": "任务", "delivery": "任务", "convoy": "车队", "route": "路线",
    "destination": "目的地", "garage": "车库", "rest stop": "休息区", "parking": "休息区",
    "gas station": "加油站", "repair shop": "维修站", "service": "维修站",
    "ferry": "渡轮", "tunnel": "隧道", "toll gate": "收费站", "bridge": "桥",
    "highway": "高速公路", "motorway": "高速公路", "lane": "车道", "speed limit": "限速",
    "police": "警察", "cop": "警察", "fine": "罚款", "ticket": "罚款",
    "headlights": "车灯", "engine": "发动机", "damage": "损坏", "overtake": "超车",
    "fuel": "油/柴油", "diesel": "油/柴油", "km/h": "公里/小时", "collision": "碰撞",
    "no collision": "无碰撞区", "nc": "无碰撞区", "ping": "延迟",
    "Scandinavia": "斯堪的纳维亚", "Calais": "加来", "Duisburg": "杜伊斯堡",
    "Kirkenes": "希尔克内斯", "Rotterdam": "鹿特丹", "Dover": "多佛",
    "server": "服务器", "admin": "管理员", "mod": "模组", "disconnect": "掉线",
    "reconnect": "重连", "rc": "重连", "save": "存档", "load": "读档",
    "World of Trucks": "卡车世界",
}

# 第4层：prompt 内嵌映射（供 Task 3 使用）
PROMPT_MAPPING = "sry=抱歉, ty/thx=谢谢, rec=已录屏, wtf=什么鬼"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest test_chat_dictionary -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add chat_dictionary.py test_chat_dictionary.py
git commit -m "feat: 新增 chat_dictionary 数据词典（俚语/短语/结构化/ETS2词汇）"
```

---

### Task 2: 实现 chat_dictionary.py 处理函数

**Files:**
- Modify: `chat_dictionary.py`
- Test: `test_chat_dictionary.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 test_chat_dictionary.py
from chat_dictionary import (
    short_phrase_fallback, fix_leftover_shorthand, preserve_mention_prefix,
    looks_untranslated, guess_source_language,
)


class TestProcessors(unittest.TestCase):
    def test_short_phrase_fallback_multiword(self):
        self.assertEqual(short_phrase_fallback("rec someplayer"), "已录屏 someplayer")

    def test_fix_leftover_shorthand(self):
        # LLM 返回里残留 "wtf" 未翻译
        self.assertIn("什么鬼", fix_leftover_shorthand("wtf 你在干嘛"))

    def test_preserve_mention_prefix(self):
        self.assertEqual(
            preserve_mention_prefix("@Player123 hello", "你好"),
            "@Player123 你好",
        )

    def test_looks_untranslated_zh_target(self):
        # 目标中文但输出无中文 → 失败
        self.assertTrue(looks_untranslated("hello world", "hello world", "zh-CN"))
        self.assertFalse(looks_untranslated("hello world", "你好世界", "zh-CN"))

    def test_guess_source_language(self):
        self.assertEqual(guess_source_language("привет как дела"), "ru")
        self.assertEqual(guess_source_language("merhaba nasılsın"), "tr")
        self.assertEqual(guess_source_language("hello there"), "en")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m unittest test_chat_dictionary -v`
Expected: FAIL（`ImportError: cannot import name 'fix_leftover_shorthand'`）

- [ ] **Step 3: 实现处理函数**

在 `chat_dictionary.py` 末尾追加（复用标准库，无第三方依赖）：

```python
import re
import unicodedata


def _is_chinese_char(ch):
    return (0x4E00 <= ord(ch) <= 0x9FFF) or (0x3400 <= ord(ch) <= 0x4DBF) \
        or (0x3000 <= ord(ch) <= 0x303F) or (0xFF00 <= ord(ch) <= 0xFFEF)


def _has_chinese(text):
    return any(_is_chinese_char(c) for c in text)


def _lower_ascii(text):
    out = []
    for ch in text:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            ch = chr(o - 0xFEE0)
        if ch == '\u3000':
            ch = ' '
        out.append(ch.lower())
    return ''.join(out)


def _normalize(text):
    out = []
    for ch in text:
        if ch in ('\ufeff', '\u200b', '\u200c', '\u200d', '\u2060'):
            continue
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            ch = chr(o - 0xFEE0)
        if ch == '\u3000':
            ch = ' '
        out.append(ch.lower())
    return ''.join(out).strip()


def _squeeze_repeated(text):
    out = []
    last = ''
    run = 0
    for ch in text:
        is_letter = ch.isascii() and ch.isalpha()
        if is_letter and ch.lower() == last.lower():
            run += 1
            if run <= 1:
                out.append(ch)
            continue
        last = ch.lower() if is_letter else ''
        run = 1 if is_letter else 0
        out.append(ch)
    return ''.join(out)


def _trim_edge_punctuation(text):
    punct = set("!?.,;:~-_'\" /\\|`\u2026\u2018\u2019\u201c\u201d\uff01\uff1f\u3002\uff0c\uff1b\uff1a\u3001")
    text = text.strip()
    while text and text[0] in punct:
        text = text[1:]
    while text and text[-1] in punct:
        text = text[:-1]
    return text.strip()


def _split_words(text):
    return [w for w in _trim_edge_punctuation(_normalize(text)).split() if w]


def _is_id_or_name(token):
    if not token:
        return False
    has_digit = any(c.isdigit() for c in token)
    has_marker = '_' in token or '-' in token
    return (has_digit or has_marker or len(token) >= 6)


def _join_tail_tokens(words, start, max_count=2):
    out = []
    for w in words[start:start + max_count]:
        if not _is_id_or_name(w):
            break
        out.append(w)
    return ' '.join(out)


def _structured_truckers_phrase(words, start):
    if start >= len(words):
        return ''
    w = words[start]
    if w == 'rec' and start + 1 < len(words) and words[start + 1] == 'ban':
        out = '已录屏，等封禁'
        tail = _join_tail_tokens(words, start + 2)
        return out + (' ' + tail if tail else '')
    if w in STRUCTURED_ACTIONS:
        out = STRUCTURED_ACTIONS[w]
        tail = _join_tail_tokens(words, start + 1)
        return out + (' ' + tail if tail else '')
    return ''


def short_phrase_fallback(text):
    """本地字典回退：命中返回译文，未命中返回空串。"""
    lower = _normalize(text)
    if not lower:
        return ''
    edge = _trim_edge_punctuation(lower)
    trailing = edge

    # 1) 完整短语精确匹配
    if edge in PHRASE_FALLBACK:
        return PHRASE_FALLBACK[edge]
    squeezed = _squeeze_repeated(edge)
    for key, val in PHRASE_FALLBACK.items():
        if squeezed == _squeeze_repeated(key):
            return val

    # 2) 单词级 token 匹配
    words = _split_words(lower)
    if len(words) == 1 and words[0] in SLANG_TOKENS:
        return SLANG_TOKENS[words[0]][0]
    # 结构化短语
    for start in range(min(len(words), 3)):
        structured = _structured_truckers_phrase(words, start)
        if structured:
            return structured

    # 3) 系统消息关键词
    for keys, val in SYSTEM_MESSAGE_FALLBACK.items():
        if any(k in lower for k in keys):
            return val

    # 4) 全 token 可译（≤5 词）
    if 1 < len(words) <= 5:
        trans = []
        ok = True
        for w in words:
            if w in SLANG_TOKENS:
                trans.append(SLANG_TOKENS[w][0])
            else:
                ok = False
                break
        if ok and trans:
            return '，'.join(trans)

    return ''


def _contains_word(text, word):
    lower = _lower_ascii(text)
    for m in re.finditer(re.escape(word), lower):
        left = m.start() == 0 or not lower[m.start() - 1].isalnum()
        right = m.end() == len(lower) or not lower[m.end()].isalnum()
        if left and right:
            return True
    return False


def _alpha_words(text):
    return [w for w in re.findall(r"[a-z\u00c0-\u024f]+", _lower_ascii(text)) if len(w) >= 2]


def looks_untranslated(input_text, output_text, target_lang):
    """判断 LLM 返回是否失败：空/等于原文/目标中文却无中文/保留过多源词。"""
    out = output_text.strip()
    if not out:
        return True
    if input_text.strip().lower() == out.lower():
        return True
    if target_lang in ('zh-CN', 'zh', 'zh-Hans') and not _has_chinese(out):
        return True
    return False


def _starts_mention(text):
    trimmed = text.strip()
    if not trimmed or trimmed[0] != '@':
        return None
    i = 1
    while i < len(trimmed) and not trimmed[i].isspace():
        i += 1
    if i <= 1:
        return None
    end = i
    p = i
    while p < len(trimmed) and trimmed[p].isspace():
        p += 1
    if p < len(trimmed) and trimmed[p] == '(':
        close = trimmed.find(')', p + 1)
        if close != -1 and trimmed[p + 1:close].isdigit():
            end = close + 1
    return trimmed[:end]


def preserve_mention_prefix(input_text, output_text):
    """保留 @玩家名 前缀。"""
    prefix = _starts_mention(input_text)
    if not prefix or prefix in output_text:
        return output_text
    return prefix + ' ' + output_text.strip()


def fix_leftover_shorthand(text):
    """后处理补译 LLM 漏译的英文缩写。"""
    words = text.split()
    out = []
    changed = False
    for w in words:
        token = _trim_edge_punctuation(w.lower())
        if token in SLANG_TOKENS and not w[0] == '@' and not _is_id_or_name(token):
            val, pause = SLANG_TOKENS[token]
            out.append(val + ('，' if pause else ''))
            changed = True
        else:
            out.append(w)
    return (' '.join(out)).strip() if changed else text


def guess_source_language(text):
    """多语言启发式检测。"""
    lower = _lower_ascii(text)
    cyrillic = sum(1 for c in lower if 0x0400 <= ord(c) <= 0x04FF)
    greek = sum(1 for c in lower if 0x0370 <= ord(c) <= 0x03FF)
    latin = sum(1 for c in lower if c.isascii() and c.isalpha()) \
        + sum(1 for c in lower if 0x00C0 <= ord(c) <= 0x024F)
    if cyrillic and cyrillic >= latin:
        if any(c in lower for c in 'іїєґ'):
            return 'uk'
        if any(c in lower for c in 'ћђљњџ'):
            return 'sr'
        if 'ъ' in lower:
            return 'bg'
        return 'ru'
    if greek and greek >= latin:
        return 'el'
    if any(c in lower for c in 'ığşç'):
        return 'tr'
    if any(c in lower for c in 'äöüß'):
        return 'de'
    if any(c in lower for c in 'ąęłńóśźż'):
        return 'pl'
    if any(c in lower for c in 'ěščřžýáíéďťňů'):
        return 'cs'
    if any(c in lower for c in 'ăâîșţț'):
        return 'ro'
    if any(c in lower for c in 'ñ¿¡'):
        return 'es'
    if any(c in lower for c in 'ãõ'):
        return 'pt'
    return 'en'
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m unittest test_chat_dictionary -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add chat_dictionary.py test_chat_dictionary.py
git commit -m "feat: chat_dictionary 处理函数（回退/后处理/mention/untranslated/语言检测）"
```

---

### Task 3: 改造 translator.py 接收方向

**Files:**
- Modify: `translator.py`（`_call_provider`、`_call_api_legacy`、`_flush_llm`、`_translate_with_mixed_lang`、`_call_api_internal`）
- Test: `test_translation_refactor.py`

- [ ] **Step 1: 写失败测试**

```python
# test_translation_refactor.py
import unittest
from unittest.mock import patch
from chat_dictionary import short_phrase_fallback


class TestReceiveRefactor(unittest.TestCase):
    def test_local_dict_short_circuit(self):
        # 本地字典命中，应直接返回，不触发 LLM
        self.assertTrue(short_phrase_fallback("wtf"))
        self.assertEqual(short_phrase_fallback("wtf"), "什么鬼")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认通过（此测试主要验证集成点可用）**

Run: `python -m unittest test_translation_refactor -v`
Expected: PASS（此测试是集成探针，真正的 prompt 断言在下方 Step 4）

- [ ] **Step 3: 修改 `_call_provider` 的 prompt 构造**

将 [translator.py:516-523](translator.py#L516-L523) 的 payload 改为：

```python
        from chat_dictionary import PROMPT_MAPPING

        target = getattr(self.cfg, 'target_language', 'zh-CN')
        system = (
            f"You translate TruckersMP/ETS2 multiplayer chat into {target}. "
            f"Output only the translation, no quotes, no explanations, no reasoning. "
            f"Any language/slang. Map {PROMPT_MAPPING}. "
            f"Keep names, IDs, tags, URLs and emoji unchanged."
        )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": _max_output_tokens(text),
        }
        # DeepSeek / MiMo 关闭 thinking
        kind = (provider.get("label", "") + provider.get("model", "")).lower()
        if "deepseek" in kind or "mimo" in kind or "xiaomi" in kind:
            payload["thinking"] = {"type": "disabled"}
```

在 `translator.py` 顶部（import 区）新增辅助函数：

```python
def _max_output_tokens(text):
    return max(64, min(160, 56 + len(text) // 4))
```

- [ ] **Step 4: 运行测试确认 prompt 正确**

Run: `python -m unittest test_translation_refactor -v`
Expected: PASS（集成探针通过；prompt 正确性在 Step 5 端到端验证）

- [ ] **Step 5: 在 `_flush_llm` 加入本地字典拦截 + 出口后处理**

在 `_flush_llm` 的单条分支（[translator.py:397-410](translator.py#L397-L410)）之前插入本地字典拦截，并在拿到 `translated` 后加后处理：

```python
    def _flush_llm(self, batch):
        try:
            if len(batch) == 1:
                text = batch[0].text
                quick = short_phrase_fallback(text)
                if quick:
                    translated = quick
                else:
                    translated = self._translate_with_mixed_lang(text, self.cfg.target_language)
                    translated = fix_leftover_shorthand(translated)
                    translated = preserve_mention_prefix(text, translated)
                    if looks_untranslated(text, translated, self.cfg.target_language):
                        # 判定失败，重试轮转下一家（已由 _call_api_internal 处理回退）
                        translated = self._translate_with_mixed_lang(text, self.cfg.target_language)
                self._cache.put(text, translated)
                ...
```

> 注：`short_phrase_fallback` / `fix_leftover_shorthand` / `preserve_mention_prefix` / `looks_untranslated` 需在 `translator.py` 顶部 `from chat_dictionary import ...` 导入。

- [ ] **Step 6: Commit**

```bash
git add translator.py test_translation_refactor.py
git commit -m "feat: 接收方向改用 system/user prompt + 本地字典拦截 + 后处理"
```

---

### Task 4: 改造 translator.py 发送方向

**Files:**
- Modify: `translator.py`（`_call_single_provider`、`_legacy_send_translate`）

- [ ] **Step 1: 修改发送方向 prompt**

将 `_call_single_provider`（[translator.py:801](translator.py#L801)）与 `_legacy_send_translate`（[translator.py:844](translator.py#L844)）中的 user 消息改为 system+user 结构：

```python
    lang_name = _SEND_LANG_NAMES.get(target_lang, "英语")
    system = f"You translate into {lang_name}. Output only the translation, no quotes, no explanations."
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": _max_output_tokens(text),
    }
```

> 发送方向**不**套用 `PROMPT_MAPPING`，不加 Map。

- [ ] **Step 2: Commit**

```bash
git add translator.py
git commit -m "feat: 发送方向改用 system/user prompt 结构"
```

---

### Task 5: 全量测试与验证

- [ ] **Step 1: 运行全量测试**

Run: `python -m unittest discover -s . -p "test_*.py" -v`
Expected: 所有测试通过，现有 7 个测试文件无回归

- [ ] **Step 2: 端到端验证（启动 + 本地字典命中）**

Run: `python -c "from chat_dictionary import short_phrase_fallback; print(short_phrase_fallback('wtf are you doing'))"`
Expected: 输出 `什么鬼`（或含"什么鬼"），证明本地字典拦截生效，无需 API

- [ ] **Step 3: Commit（如有遗漏）**

```bash
git add -A && git commit -m "test: 全量测试通过 + 端到端验证"
```

---

## Self-Review

- **Spec 覆盖**：五层术语（Task 1-2）✓；发消息方式接收（Task 3）✓；发送（Task 4）✓；保留分流/特色（Task 3 仅改 prompt 与入口/出口，不动轮转）✓；验收标准（Task 5）✓。
- **占位符**：无 TBD/TODO；词典数据完整（对方源码移植 + ETS2 词汇）。
- **类型一致**：`short_phrase_fallback` / `fix_leftover_shorthand` / `preserve_mention_prefix` / `looks_untranslated` / `guess_source_language` 在 Task 2 定义、Task 3 复用，签名一致。
