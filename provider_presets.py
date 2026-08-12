"""
Provider presets for ETS2 Chat Translator.
Built-in provider templates covering domestic and international LLM APIs.
Users can extend via prompts/presets.json.
"""
from dataclasses import dataclass, field


@dataclass
class ProviderPreset:
    """Pre-configured provider template."""
    id: str                     # unique preset ID, e.g. "deepseek"
    name: str                   # display name, e.g. "DeepSeek"
    website_url: str            # official website
    api_key_url: str            # where to get API key
    endpoint: str               # base URL (without /chat/completions)
    api_format: str             # "openai" or "anthropic"
    default_model: str          # recommended model
    models_url: str             # model list endpoint, "" if not supported
    icon: str                   # icon filename stem
    icon_color: str             # hex color for icon accent
    category: str               # "recommended"|"cn_cloud"|"intl_cloud"|"local"
    template_headers: dict = field(default_factory=dict)
    template_body: dict = field(default_factory=dict)
    description: str = ""
    recommended: bool = False

    def build_endpoint(self) -> str:
        """Build full chat completions endpoint from base URL."""
        base = self.endpoint.rstrip("/")
        if self.api_format == "anthropic":
            return f"{base}/v1/messages"
        return f"{base}/v1/chat/completions"

    def to_provider_dict(self) -> dict:
        """Convert preset to provider config dict for storage."""
        return {
            "id": self.id,
            "label": self.name,
            "endpoint": self.build_endpoint(),
            "api_key": "",
            "model": self.default_model,
            "enabled": True,
            "preset_id": self.id,
            "icon": self.icon,
            "api_format": self.api_format,
            "weight": 100,
            "extra_headers": dict(self.template_headers),
            "extra_body": dict(self.template_body),
            "timeout": 8,
        }


# ── Icon name → unicode symbol mapping (Tkinter compatible) ──
PROVIDER_ICONS: dict[str, str] = {
    "deepseek": "🐋",
    "siliconflow": "🏔️",
    "openai": "🤖",
    "groq": "⚡",
    "ollama": "🦙",
    "dashscope": "☁️",
    "zhipu": "🧠",
    "kimi": "🌟",
    "doubao": "🫘",
    "baidu": "🌐",
    "xunfei": "🎤",
    "hunyuan": "💬",
    "stepfun": "🚀",
    "anthropic": "🧪",
    "gemini": "💎",
    "mistral": "🌬️",
    "cohere": "🔗",
    "together": "🤝",
    "openrouter": "🔀",
    "vllm": "🖥️",
    "custom": "✏️",
}

# ── Category definitions ──
CATEGORIES = [
    ("recommended", "⭐ 推荐"),
    ("cn_cloud", "☁️ 国内云"),
    ("intl_cloud", "🌍 国际"),
    ("local", "🏠 本地"),
]

CATEGORY_ORDER = {cat: i for i, (cat, _) in enumerate(CATEGORIES)}
CATEGORY_LABELS = dict(CATEGORIES)


# ═══════════════════════════════════════════════════════
#  Preset definitions (20+ providers)
# ═══════════════════════════════════════════════════════

PRESETS: list[ProviderPreset] = [
    # ── ⭐ Recommended ──
    ProviderPreset(
        id="siliconflow", name="硅基流动 (SiliconFlow)",
        website_url="https://siliconflow.cn/", api_key_url="https://cloud.siliconflow.cn/account/ak",
        endpoint="https://api.siliconflow.cn", api_format="openai",
        default_model="Qwen/Qwen3-8B", models_url="/v1/models",
        icon="siliconflow", icon_color="#6C5CE7",
        category="recommended", recommended=True,
        description="国内直连，免费额度，不限并发",
    ),
    ProviderPreset(
        id="deepseek", name="DeepSeek",
        website_url="https://platform.deepseek.com/", api_key_url="https://platform.deepseek.com/api_keys",
        endpoint="https://api.deepseek.com", api_format="openai",
        default_model="deepseek-chat", models_url="/v1/models",
        icon="deepseek", icon_color="#4B6BF5",
        category="recommended", recommended=True,
        description="翻译质量极佳，¥1/1M tokens",
    ),
    ProviderPreset(
        id="openai", name="OpenAI",
        website_url="https://platform.openai.com/", api_key_url="https://platform.openai.com/api-keys",
        endpoint="https://api.openai.com", api_format="openai",
        default_model="gpt-4o-mini", models_url="/v1/models",
        icon="openai", icon_color="#10A37F",
        category="recommended", recommended=True,
        description="$0.15/1M tokens，便宜可靠",
    ),
    ProviderPreset(
        id="groq", name="Groq",
        website_url="https://groq.com/", api_key_url="https://console.groq.com/keys",
        endpoint="https://api.groq.com/openai", api_format="openai",
        default_model="llama-3.3-70b-versatile", models_url="/v1/models",
        icon="groq", icon_color="#F55036",
        category="recommended", recommended=False,
        description="推理速度极快，免费额度",
    ),
    ProviderPreset(
        id="ollama", name="Ollama (本地)",
        website_url="https://ollama.com/", api_key_url="",
        endpoint="http://localhost:11434", api_format="openai",
        default_model="qwen3:8b", models_url="",
        icon="ollama", icon_color="#FFFFFF",
        category="recommended", recommended=False,
        description="本地运行，无需网络，隐私安全",
    ),

    # ── ☁️ 国内云 ──
    ProviderPreset(
        id="dashscope", name="阿里百炼 (DashScope)",
        website_url="https://dashscope.aliyun.com/", api_key_url="https://dashscope.console.aliyun.com/apiKey",
        endpoint="https://dashscope.aliyuncs.com/compatible-mode", api_format="openai",
        default_model="qwen-turbo", models_url="/v1/models",
        icon="dashscope", icon_color="#FF6A00",
        category="cn_cloud", description="阿里云通义千问系列",
    ),
    ProviderPreset(
        id="zhipu", name="智谱 GLM",
        website_url="https://open.bigmodel.cn/", api_key_url="https://open.bigmodel.cn/usercenter/apikeys",
        endpoint="https://open.bigmodel.cn/api/paas/v4", api_format="openai",
        default_model="glm-4-flash", models_url="/v1/models",
        icon="zhipu", icon_color="#3859F3",
        category="cn_cloud", description="清华智谱 GLM 系列",
    ),
    ProviderPreset(
        id="kimi", name="Kimi (月之暗面)",
        website_url="https://platform.kimi.com/", api_key_url="https://platform.kimi.com/api",
        endpoint="https://api.moonshot.cn", api_format="openai",
        default_model="kimi-k2.7-code", models_url="/v1/models",
        icon="kimi", icon_color="#6366F1",
        category="cn_cloud", description="月之暗面 Moonshot 系列",
    ),
    ProviderPreset(
        id="doubao", name="豆包 (字节跳动)",
        website_url="https://console.volcengine.com/ark/", api_key_url="https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey",
        endpoint="https://ark.cn-beijing.volces.com/api/v3", api_format="openai",
        default_model="doubao-pro-32k", models_url="/v1/models",
        icon="doubao", icon_color="#3370FF",
        category="cn_cloud", description="字节跳动豆包系列",
    ),
    ProviderPreset(
        id="baidu_qianfan", name="百度千帆",
        website_url="https://qianfan.cloud.baidu.com/", api_key_url="https://console.bce.baidu.com/qianfan/ais/console/applicationConsole/application",
        endpoint="https://qianfan.baidubce.com/v2", api_format="openai",
        default_model="ernie-speed-128k", models_url="",
        icon="baidu", icon_color="#2932E1",
        category="cn_cloud", description="百度文心一言系列",
    ),
    ProviderPreset(
        id="xunfei", name="讯飞星火",
        website_url="https://xinghuo.xfyun.cn/", api_key_url="https://console.xfyun.cn/services/bm3",
        endpoint="https://spark-api-open.xf-yun.com/v1", api_format="openai",
        default_model="spark-lite", models_url="",
        icon="xunfei", icon_color="#1E6FFF",
        category="cn_cloud", description="讯飞星火认知大模型",
    ),
    ProviderPreset(
        id="hunyuan", name="腾讯混元",
        website_url="https://cloud.tencent.com/product/hunyuan", api_key_url="https://console.cloud.tencent.com/hunyuan/api-key",
        endpoint="https://api.hunyuan.cloud.tencent.com/v1", api_format="openai",
        default_model="hunyuan-lite", models_url="/v1/models",
        icon="hunyuan", icon_color="#00A4FF",
        category="cn_cloud", description="腾讯混元大模型",
    ),
    ProviderPreset(
        id="stepfun", name="阶跃星辰",
        website_url="https://platform.stepfun.com/", api_key_url="https://platform.stepfun.com/interface-key",
        endpoint="https://api.stepfun.com/v1", api_format="openai",
        default_model="step-1-8k", models_url="/v1/models",
        icon="stepfun", icon_color="#00D4AA",
        category="cn_cloud", description="阶跃星辰 Step 系列",
    ),

    # ── 🌍 国际 ──
    ProviderPreset(
        id="anthropic", name="Claude API (Anthropic)",
        website_url="https://www.anthropic.com/", api_key_url="https://console.anthropic.com/settings/keys",
        endpoint="https://api.anthropic.com", api_format="anthropic",
        default_model="claude-sonnet-4-20250514", models_url="",
        icon="anthropic", icon_color="#D4915D",
        category="intl_cloud",
        template_headers={"x-api-key": "{api_key}", "anthropic-version": "2023-06-01"},
        description="Claude 官方 Anthropic Messages API",
    ),
    ProviderPreset(
        id="gemini", name="Gemini (Google)",
        website_url="https://ai.google.dev/", api_key_url="https://aistudio.google.com/apikey",
        endpoint="https://generativelanguage.googleapis.com/v1beta", api_format="openai",
        default_model="gemini-2.0-flash", models_url="",
        icon="gemini", icon_color="#4285F4",
        category="intl_cloud", description="Google Gemini 系列",
    ),
    ProviderPreset(
        id="mistral", name="Mistral AI",
        website_url="https://mistral.ai/", api_key_url="https://console.mistral.ai/api-keys/",
        endpoint="https://api.mistral.ai", api_format="openai",
        default_model="mistral-small", models_url="/v1/models",
        icon="mistral", icon_color="#F04D2D",
        category="intl_cloud", description="欧洲领先 AI 实验室",
    ),
    ProviderPreset(
        id="cohere", name="Cohere",
        website_url="https://cohere.com/", api_key_url="https://dashboard.cohere.com/api-keys",
        endpoint="https://api.cohere.com/v1", api_format="openai",
        default_model="command-r", models_url="/v1/models",
        icon="cohere", icon_color="#39594D",
        category="intl_cloud", description="企业级 AI 平台",
    ),
    ProviderPreset(
        id="together", name="Together AI",
        website_url="https://www.together.ai/", api_key_url="https://api.together.ai/settings/api-keys",
        endpoint="https://api.together.xyz/v1", api_format="openai",
        default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo", models_url="/v1/models",
        icon="together", icon_color="#0F6FFF",
        category="intl_cloud", description="开源模型托管，速度快",
    ),
    ProviderPreset(
        id="openrouter", name="OpenRouter",
        website_url="https://openrouter.ai/", api_key_url="https://openrouter.ai/keys",
        endpoint="https://openrouter.ai/api/v1", api_format="openai",
        default_model="openai/gpt-4o-mini", models_url="/v1/models",
        icon="openrouter", icon_color="#6366F1",
        category="intl_cloud", description="聚合路由，多模型统一访问",
    ),

    # ── 🏠 本地 ──
    ProviderPreset(
        id="ollama_local", name="Ollama (本地)",
        website_url="https://ollama.com/", api_key_url="",
        endpoint="http://localhost:11434", api_format="openai",
        default_model="qwen3:8b", models_url="",
        icon="ollama", icon_color="#FFFFFF",
        category="local", description="本地 LLM，无需网络",
    ),
    ProviderPreset(
        id="vllm", name="vLLM (自部署)",
        website_url="https://docs.vllm.ai/", api_key_url="",
        endpoint="http://localhost:8000", api_format="openai",
        default_model="", models_url="/v1/models",
        icon="vllm", icon_color="#00BFA5",
        category="local", description="高性能本地推理引擎",
    ),

    # ── 百度翻译 ──
    ProviderPreset(
        id="baidu",
        name="百度翻译",
        website_url="https://fanyi-api.baidu.com/",
        api_key_url="https://fanyi-api.baidu.com/api/trans/product/desktop",
        endpoint="https://fanyi-api.baidu.com/api/trans/vip/translate",
        api_format="baidu",
        default_model="通用翻译",
        models_url="",
        icon="baidu",
        icon_color="#3385FF",
        category="cn_cloud",
        template_headers={},
        template_body={},
        description="百度翻译 API，标准版每月 500 万字符免费",
        recommended=False,
    ),
]


# ── Lookup helpers ──
_PRESET_BY_ID: dict[str, ProviderPreset] = {p.id: p for p in PRESETS}


def get_preset(preset_id: str) -> ProviderPreset | None:
    """Get a preset by its ID. Returns None if not found."""
    return _PRESET_BY_ID.get(preset_id)


def get_presets_by_category() -> dict[str, list[ProviderPreset]]:
    """Group presets by category."""
    result: dict[str, list[ProviderPreset]] = {}
    for p in PRESETS:
        result.setdefault(p.category, []).append(p)
    return result


def get_all_presets() -> list[ProviderPreset]:
    """Return all presets in display order."""
    return list(PRESETS)


def match_preset_from_endpoint(endpoint: str) -> str:
    """Try to guess a preset ID from an endpoint URL. Returns '' if no match."""
    if not endpoint:
        return ""
    ep_lower = endpoint.lower()
    for preset in PRESETS:
        base = preset.endpoint.lower()
        if base and base in ep_lower:
            return preset.id
    return ""
