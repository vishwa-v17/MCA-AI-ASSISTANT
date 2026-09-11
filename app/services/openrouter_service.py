import os
import time
import threading
import requests

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
CACHE_TTL_SECONDS = int(os.getenv("OPENROUTER_MODEL_CACHE_TTL", "900"))
FREE_ROUTER_ID = "openrouter/free"

_models_cache = {"expires_at": 0.0, "models": []}
_models_lock = threading.Lock()
_http = requests.Session()


def get_server_api_key():
    return (os.getenv("OPENROUTER_API_KEY") or "").strip()


def get_default_model():
    return (os.getenv("DEFAULT_OPENROUTER_MODEL") or FREE_ROUTER_ID).strip()


def _headers(api_key):
    headers = {
        "Accept": "application/json",
        "X-Title": "MCA AI Assistant",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def fetch_models(api_key, force=False):
    """Return OpenRouter's current model catalog, cached server-side."""
    now = time.time()
    with _models_lock:
        if not force and _models_cache["models"] and now < _models_cache["expires_at"]:
            return list(_models_cache["models"]), None

    try:
        response = _http.get(
            OPENROUTER_MODELS_URL,
            headers=_headers(api_key),
            timeout=15,
        )
        if response.status_code != 200:
            return [], f"OpenRouter model catalog returned HTTP {response.status_code}."

        payload = response.json()
        models = payload.get("data", [])
        if not isinstance(models, list):
            return [], "OpenRouter returned an invalid model catalog."

        with _models_lock:
            _models_cache["models"] = models
            _models_cache["expires_at"] = time.time() + CACHE_TTL_SECONDS

        return list(models), None
    except requests.RequestException:
        return [], "Could not reach OpenRouter to load the model catalog."
    except ValueError:
        return [], "OpenRouter returned invalid model data."


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_free_text_model(model):
    pricing = model.get("pricing") or {}
    prompt = _to_float(pricing.get("prompt"))
    completion = _to_float(pricing.get("completion"))
    if prompt != 0.0 or completion != 0.0:
        return False

    architecture = model.get("architecture") or {}
    modality = str(architecture.get("modality") or "").lower()
    if modality and "text" not in modality:
        return False

    model_id = str(model.get("id") or "").lower()
    blocked = ("embedding", "embed-", "rerank", "tts", "speech", "transcription", "image")
    return not any(token in model_id for token in blocked)


def _model_label(model):
    return model.get("name") or model.get("id") or "Unknown model"


def normalize_model(model):
    architecture = model.get("architecture") or {}
    provider = str(model.get("id") or "").split("/", 1)[0] if "/" in str(model.get("id") or "") else ""
    return {
        "id": model.get("id"),
        "name": _model_label(model),
        "provider": provider,
        "context_length": model.get("context_length"),
        "pricing": model.get("pricing") or {},
        "free": is_free_text_model(model),
        "description": model.get("description") or "",
        "supported_parameters": model.get("supported_parameters") or [],
        "modality": architecture.get("modality"),
    }


def get_model_catalog(api_key, force=False):
    models, error = fetch_models(api_key, force=force)
    if error:
        return None, error

    normalized = [normalize_model(m) for m in models if m.get("id")]
    normalized.sort(key=lambda m: (not m["free"], -(m["context_length"] or 0), m["name"].lower()))

    return {
        "free_models": [m for m in normalized if m["free"]],
        "all_models": normalized,
        "free_router": {
            "id": FREE_ROUTER_ID,
            "name": "OpenRouter Free Router",
            "provider": "OpenRouter",
            "free": True,
            "description": "Automatically selects an available free model.",
            "context_length": 200000,
        },
    }, None


def validate_model(model_id, api_key, force_refresh=False):
    model_id = (model_id or "").strip()
    if not model_id:
        return False

    if model_id == FREE_ROUTER_ID:
        return True

    models, error = fetch_models(api_key, force=force_refresh)
    if error:
        return False

    return any(str(model.get("id")) == model_id for model in models)


def mask_key_last4(last4):
    return f"••••••••••••{last4}" if last4 else "Configured"
