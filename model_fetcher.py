"""
Model list fetcher for ETS2 Chat Translator.
Fetches available models from OpenAI-compatible /v1/models endpoints.
"""
import httpx
from dataclasses import dataclass, field


@dataclass
class FetchResult:
    """Result of a model fetch operation."""
    success: bool
    models: list[str] = field(default_factory=list)
    error: str = ""
    latency_ms: float = 0.0


def fetch_models(
    endpoint: str,
    api_key: str = "",
    timeout: float = 8.0,
) -> FetchResult:
    """Fetch available model names from an OpenAI-compatible endpoint.

    Strips the /chat/completions suffix if present, then calls GET /v1/models.

    Args:
        endpoint: Full endpoint URL (e.g., https://api.deepseek.com/v1/chat/completions)
        api_key: API key for authentication
        timeout: HTTP timeout in seconds

    Returns:
        FetchResult with model names on success, error message on failure.
    """
    import time
    start = time.monotonic()

    # Derive base URL from endpoint
    base = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/v1/chat/completions", "/v1/messages"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break

    models_url = f"{base}/v1/models"

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        client = httpx.Client(timeout=timeout)
        try:
            resp = client.get(models_url, headers=headers)
            latency = (time.monotonic() - start) * 1000

            if resp.status_code == 200:
                data = resp.json()
                models = _parse_openai_model_list(data)
                if models:
                    return FetchResult(
                        success=True, models=models, latency_ms=round(latency, 1)
                    )
                return FetchResult(
                    success=False,
                    error="API returned empty model list",
                    latency_ms=round(latency, 1),
                )

            # Non-200: try to extract error detail
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except Exception:
                detail = ""
            if not detail:
                detail = f"HTTP {resp.status_code}"

            return FetchResult(
                success=False,
                error=detail,
                latency_ms=round(latency, 1),
            )

        finally:
            client.close()

    except httpx.ConnectTimeout:
        latency = (time.monotonic() - start) * 1000
        return FetchResult(success=False, error="Connection timeout", latency_ms=round(latency, 1))
    except httpx.ConnectError:
        latency = (time.monotonic() - start) * 1000
        return FetchResult(success=False, error="Cannot connect to server", latency_ms=round(latency, 1))
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return FetchResult(success=False, error=str(e)[:120], latency_ms=round(latency, 1))


def _parse_openai_model_list(data: dict) -> list[str]:
    """Parse model names from OpenAI /v1/models response format."""
    items = data.get("data", [])
    if not isinstance(items, list):
        return []

    models = []
    for item in items:
        if isinstance(item, dict):
            model_id = item.get("id", "")
        elif isinstance(item, str):
            model_id = item
        else:
            continue
        if model_id and isinstance(model_id, str):
            models.append(model_id.strip())

    # Sort: put non-preview/stable models first
    def sort_key(name: str) -> tuple:
        is_preview = any(tag in name.lower() for tag in ("preview", "beta", "alpha", "deprecated"))
        return (1 if is_preview else 0, name.lower())

    models.sort(key=sort_key)
    return models


def test_connectivity(
    endpoint: str,
    api_key: str = "",
    timeout: float = 8.0,
) -> FetchResult:
    """Quick connectivity test — checks if endpoint is reachable.

    Uses fetch_models as a lightweight probe. If /v1/models fails, tries a
    simple GET on the base URL to confirm server reachability.
    """
    result = fetch_models(endpoint, api_key, timeout)
    if result.success:
        return result

    # Fallback: try base URL directly
    import time
    base = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/v1/chat/completions", "/v1/messages"):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.monotonic()
    try:
        client = httpx.Client(timeout=timeout)
        try:
            resp = client.get(base, headers=headers)
            latency = (time.monotonic() - start) * 1000
            if resp.status_code < 500:
                return FetchResult(
                    success=True,
                    models=[],
                    latency_ms=round(latency, 1),
                )
            return FetchResult(
                success=False,
                error=f"Server error HTTP {resp.status_code}",
                latency_ms=round(latency, 1),
            )
        finally:
            client.close()
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return FetchResult(
            success=False,
            error=str(e)[:120],
            latency_ms=round(latency, 1),
        )
