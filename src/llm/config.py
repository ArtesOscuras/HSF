import json
import os
from src.hsf_paths import settings_file as _settings_dir

_LLM_CONFIG_FILE = os.path.join(os.path.dirname(str(_settings_dir())), "llm.json")

_DEFAULTS = {
    "providers": {
        "ollama": {
            "name": "Ollama (local)",
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
            "models": ["llama3.2:3b"],
        },
    },
    "active_provider": "ollama",
    "active_models": {},
    "prompts": {
        "consultor": (
            "You are a helpful assistant running inside a small console. "
            "Keep responses brief and to the point.\n\n"
            "Never use asterisks, underscores, backticks, brackets, "
            "or hash symbols in your responses, unless they are part "
            "of the literal content."
        ),
        "evidence_analysis": (
            "This evidence is part of a web browsing session. "
            "You need to analyze it. You have more details in the "
            "'For LLM analysis.md' file in the same directory."
        ),
    },
}


def _ensure_dir():
    d = os.path.dirname(_LLM_CONFIG_FILE)
    os.makedirs(d, exist_ok=True)


def load():
    _ensure_dir()
    if not os.path.isfile(_LLM_CONFIG_FILE):
        return dict(_DEFAULTS)
    try:
        with open(_LLM_CONFIG_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, PermissionError, OSError):
        return dict(_DEFAULTS)
    for key, val in _DEFAULTS.items():
        if key not in data:
            data[key] = val
        elif isinstance(val, dict) and isinstance(data[key], dict):
            for sub_key, sub_val in val.items():
                if sub_key not in data[key]:
                    data[key][sub_key] = sub_val
    if "active_model" in data:
        data.pop("active_model")
    if "system_prompt" in data:
        if "consultor" not in data.get("prompts", {}):
            data.setdefault("prompts", {})["consultor"] = data.pop("system_prompt")
        else:
            data.pop("system_prompt")
    return data


def save(config):
    _ensure_dir()
    try:
        with open(_LLM_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except (PermissionError, OSError):
        pass


def get_provider(config, provider_id=None):
    pid = provider_id or config.get("active_provider", "")
    providers = config.get("providers", {})
    return providers.get(pid, {})


def get_active_model(config):
    pid = config.get("active_provider", "")
    am = config.get("active_models", {}).get(pid, "")
    if am:
        return am
    provider_models = get_provider(config, pid).get("models", [])
    return provider_models[0] if provider_models else ""
