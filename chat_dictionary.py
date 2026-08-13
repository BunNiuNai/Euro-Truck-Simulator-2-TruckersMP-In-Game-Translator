"""五层术语处理：本地俚语词典 + 短语回退 + 结构化短语 + prompt 映射 + 后处理补译。

数据来源：Seven-TMP/ets2-chat-translator 的 translate_engine.cpp（直接移植），
ETS2 专有词汇为保留的原术语库。
"""
import re

# ─────────────────────────────────────────────────────────────
# 第1层：俚语 token → (译文, pauseAfter)
# ─────────────────────────────────────────────────────────────
SLANG_TOKENS = {
    # 缩写/感叹
    "wtf": ("什么鬼", True), "wdf": ("什么鬼", True), "tf": ("什么鬼", True),
    "wth": ("什么鬼", True), "wdym": ("你什么意思", True), "wyd": ("你在干嘛", True),
    "omg": ("天啊", True), "ffs": ("真服了", True),
    "lol": ("哈哈", True), "lmao": ("哈哈", True), "rofl": ("笑死", True),
    "xd": ("哈哈", True),
    # 道歉
    "sb": ("傻逼", True), "sry": ("抱歉", True), "sr": ("抱歉", True),
    "sory": ("抱歉", True), "srry": ("抱歉", True), "srrry": ("抱歉", True),
    "sorry": ("抱歉", True), "soz": ("抱歉", True), "pardon": ("抱歉", True),
    "pls": ("请", False), "plz": ("请", False), "please": ("请", False),
    # 感谢
    "ty": ("谢谢", True), "tyty": ("谢谢", True), "tysm": ("非常感谢", True),
    "tyvm": ("非常感谢", True), "thx": ("谢谢", True), "tnx": ("谢谢", True),
    "tks": ("谢谢", True), "tx": ("谢谢", True), "tq": ("谢谢", True),
    "thanks": ("谢谢", True),
    # 其他缩写
    "np": ("没事", True), "nvm": ("没事", True), "brb": ("马上回", True),
    "afk": ("暂离", True), "idk": ("我不知道", True), "idc": ("无所谓", True),
    "ikr": ("就是说", True), "asap": ("尽快", True),
    "gg": ("打得好", True), "wp": ("打得好", True), "gl": ("祝好运", True),
    "hf": ("玩得开心", True),
    # 问候/告别
    "hi": ("你好", True), "hello": ("你好", True), "hey": ("嘿", True),
    "yo": ("嘿", True), "ow": ("嗷", True), "sup": ("咋样", True),
    "bye": ("再见", True), "cya": ("再见", True), "cu": ("再见", True),
    "bb": ("再见", True), "gn": ("晚安", True), "gn8": ("晚安", True),
    "gm": ("早安", True),
    # 称呼
    "bro": ("兄弟", True), "bruh": ("兄弟", True), "dude": ("老兄", True),
    "mate": ("伙计", True), "man": ("兄弟", True),
    # 是/否/简单应答
    "k": ("好", True), "kk": ("好", True), "ok": ("好的", True),
    "okay": ("好的", True), "yes": ("是", True), "y": ("是", True),
    "no": ("不", True), "n": ("不", True), "wait": ("等一下", True),
    "stop": ("停一下", True), "go": ("走", True), "slow": ("慢点", True),
    "move": ("让一下", True),
    # 游戏网络
    "lag": ("卡顿", True), "laggy": ("很卡", True),
    # 土耳其语
    "tamam": ("好的", True), "neden": ("为什么", True), "hayir": ("不", True),
    "hayır": ("不", True), "sa": ("你好", True), "as": ("你好", True),
    "gel": ("过来", True), "var": ("有", True), "varmi": ("有吗", True),
    "varmı": ("有吗", True),
    # Discord
    "dc": ("Discord", True), "ds": ("Discord", True),
    # 游戏行为/举报
    "crash": ("撞车", True), "ram": ("撞人", True), "rammer": ("撞人玩家", True),
    "rec": ("已录屏", True), "recording": ("已录屏", True),
    "report": ("举报", True), "rep": ("举报", True), "ban": ("封禁", True),
    "kick": ("踢出", True),
    # 脏话/嘲讽
    "fk": ("靠", True), "fck": ("靠", True), "fuck": ("操", True),
    "shit": ("靠", True), "damn": ("该死", True), "stfu": ("闭嘴", True),
    "fu": ("去你的", True), "trash": ("垃圾", False), "ez": ("太简单了", True),
    "idiot": ("白痴", False), "stupid": ("蠢货", False), "noob": ("菜鸟", False),
    "moron": ("蠢货", False), "clown": ("小丑", False),
}

# ─────────────────────────────────────────────────────────────
# 第2层：完整短语精确匹配 → 中文
# ─────────────────────────────────────────────────────────────
PHRASE_FALLBACK = {
    # 英文
    "thank you": "谢谢", "thank": "谢谢", "good luck": "祝好运",
    "have fun": "玩得开心", "nice lag": "卡得真漂亮", "stop horn": "别按喇叭",
    "the player stop horn": "那个玩家别按喇叭", "f7 at": "按 F7",
    "dc varmi": "有 Discord 吗", "dc varmı": "有 Discord 吗",
    "wtf is this": "什么鬼，这是啥", "what the fuck": "什么鬼",
    "what the hell": "什么鬼", "ahah": "哈哈", "ahaha": "哈哈",
    "ahahah": "哈哈", "haha": "哈哈", "hahaha": "哈哈",
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
    "onune kırma olm": "别往我前面变道，兄弟",
    "önüne kırma olum": "别往我前面变道，兄弟",
    "araba 100 oldu hasareı": "车损到 100 了", "yol vre la": "让路啊",
    "yol ver la": "让路啊",
    # 颜文字/手势
    "o/": "挥手", "o//": "挥手", "0/": "挥手", "0//": "挥手",
    "\\o": "挥手", "\\o/": "欢呼",
    ":)": "微笑", ":(": "难过", ":d": "哈哈", "<3": "爱心",
}

# ─────────────────────────────────────────────────────────────
# 第3层：结构化短语（动作 + 名字拼接）
# ─────────────────────────────────────────────────────────────
STRUCTURED_ACTIONS = {
    "rec": "已录屏", "recording": "已录屏",
    "report": "举报", "rep": "举报",
    "ban": "封禁", "kick": "踢出",
}

# 系统消息关键词回退
SYSTEM_MESSAGE_FALLBACK = {
    ("cannot connect to server", "can't connect to server", "can not connect to server"):
        "无法连接到服务器，可能是网络连接问题。",
    ("automatically reconnected", "automaticly reconnected", "reconnected within next",
     "reconnect within next"):
        "将在接下来的几秒内自动重新连接。",
    ("connection established", "connected to server"): "已连接到服务器。",
    ("connection refused", "connection timed out"): "连接失败，请检查网络或稍后重试。",
}

# ─────────────────────────────────────────────────────────────
# 保留的 ETS2 专有词汇
# ─────────────────────────────────────────────────────────────
ETS2_TERMS = {
    "truck": "卡车", "trailer": "挂车", "cargo": "货物",
    "job": "任务", "delivery": "任务", "convoy": "车队", "route": "路线",
    "destination": "目的地", "garage": "车库", "rest stop": "休息区",
    "parking": "休息区", "gas station": "加油站", "repair shop": "维修站",
    "service": "维修站", "ferry": "渡轮", "tunnel": "隧道",
    "toll gate": "收费站", "bridge": "桥", "highway": "高速公路",
    "motorway": "高速公路", "lane": "车道", "speed limit": "限速",
    "police": "警察", "cop": "警察", "fine": "罚款", "ticket": "罚款",
    "headlights": "车灯", "engine": "发动机", "damage": "损坏",
    "overtake": "超车", "fuel": "油/柴油", "diesel": "油/柴油",
    "km/h": "公里/小时", "collision": "碰撞", "no collision": "无碰撞区",
    "nc": "无碰撞区", "ping": "延迟", "Scandinavia": "斯堪的纳维亚",
    "Calais": "加来", "Duisburg": "杜伊斯堡", "Kirkenes": "希尔克内斯",
    "Rotterdam": "鹿特丹", "Dover": "多佛", "server": "服务器",
    "admin": "管理员", "mod": "模组", "disconnect": "掉线",
    "reconnect": "重连", "rc": "重连", "save": "存档", "load": "读档",
    "World of Trucks": "卡车世界",
}

# ─────────────────────────────────────────────────────────────
# 第4层：prompt 内嵌映射（供 translator.py 使用）
# ─────────────────────────────────────────────────────────────
PROMPT_MAPPING = "sry=抱歉, ty/thx=谢谢, rec=已录屏, wtf=什么鬼"


# ─────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────

def _is_chinese_char(ch):
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF) \
        or (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFFEF)


def _has_chinese(text):
    return any(_is_chinese_char(c) for c in text)


def _lower(text):
    out = []
    for ch in text:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            ch = chr(o - 0xFEE0)  # 全角 → 半角
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
    return re.sub(r'([a-zA-Z])\1+', r'\1', text)


_PUNCT = set("!?.,;:~-_'\" /\\|`\u2026\u2018\u2019\u201c\u201d"
             "\uff01\uff1f\u3002\uff0c\uff1b\uff1a\u3001")


def _trim_edge_punctuation(text):
    text = text.strip()
    while text and text[0] in _PUNCT:
        text = text[1:]
    while text and text[-1] in _PUNCT:
        text = text[:-1]
    return text.strip()


def _split_words(text):
    return [w for w in _trim_edge_punctuation(_normalize(text)).split() if w]


def _is_id_or_name(token):
    if not token:
        return False
    has_digit = any(c.isdigit() for c in token)
    has_marker = '_' in token or '-' in token
    return has_digit or has_marker or len(token) >= 6


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


# ─────────────────────────────────────────────────────────────
# 主要处理函数
# ─────────────────────────────────────────────────────────────

def short_phrase_fallback(text):
    """本地字典回退：命中返回译文，未命中返回空串。"""
    lower = _normalize(text)
    if not lower:
        return ''
    edge = _trim_edge_punctuation(lower)

    # 1) 完整短语精确匹配（俚语短语 + ETS2 多词术语）
    if edge in PHRASE_FALLBACK:
        return PHRASE_FALLBACK[edge]
    if edge in ETS2_TERMS:
        return ETS2_TERMS[edge]
    squeezed = _squeeze_repeated(edge)
    for key, val in PHRASE_FALLBACK.items():
        if squeezed == _squeeze_repeated(key):
            return val

    words = _split_words(lower)

    # 2) 单词级匹配（俚语 + ETS2 单词）
    if len(words) == 1:
        if words[0] in SLANG_TOKENS:
            return SLANG_TOKENS[words[0]][0]
        if words[0] in ETS2_TERMS:
            return ETS2_TERMS[words[0]]

    # 3) 结构化短语
    for start in range(min(len(words), 3)):
        structured = _structured_truckers_phrase(words, start)
        if structured:
            return structured

    # 4) 系统消息关键词
    for keys, val in SYSTEM_MESSAGE_FALLBACK.items():
        if any(k in lower for k in keys):
            return val

    # 5) 全 token 可译（≤5 词）
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


def looks_untranslated(input_text, output_text, target_lang):
    """判断 LLM 返回是否失败：空/等于原文/目标中文却无中文。"""
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
        if token in SLANG_TOKENS and not w.startswith('@') and not _is_id_or_name(token):
            val, pause = SLANG_TOKENS[token]
            out.append(val + ('，' if pause else ''))
            changed = True
        else:
            out.append(w)
    return ' '.join(out).strip() if changed else text


def guess_source_language(text):
    """多语言启发式检测。"""
    lower = _lower(text)
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
