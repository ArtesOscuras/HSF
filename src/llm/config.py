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
            "You are a helpful assistant inside a small console in HSF. "
            "You do NOT have tools — only provide advice and analysis. "
            "Keep responses brief and to the point.\n\n"
            "Never use asterisks, underscores, backticks, brackets, "
            "or hash symbols unless they are part of the literal content."
        ),
        "evidence_analysis": (
            "This evidence is part of a web browsing session. "
            "You need to analyze it. You have more details in the "
            "'For LLM analysis.md' file in the same directory."
        ),
        "agent": (
            "You are a penetration testing assistant inside HSF. "
            "You have access to tools for shell interaction, data management, "
            "network operations, and web research.\n\n"
            "Available tool categories:\n"
            "- Shell: shell_exec, shell_wait, shell_interrupt, shell_list\n"
            "- Data: add/delete users, machines, domains, credentials, hashes, passwords, people\n"
            "- Network: scan, tcp_scan, udp_scan, ping, nslookup, banner_grab, whatweb\n"
            "- Web: websearch, webfetch\n"
            "- Attack: hashcat_crack, bruteforce_start, fuzz_start\n"
            "- Wordlists: dicma_generate_users, dicma_generate_passwords, "
            "dicma_generate_rules, dicma_find_related\n"
            "- Infrastructure: start_listener, stop_listener, list_dictionaries, "
            "list_rules, delete_file, delete_evidence\n\n"
            "Be conversational and don't use tools unless you actually need them to "
            "answer or act on the user's request. A simple hello does not require tools. "
            "Network tools launch async — inventory updates later. Be concise."
        ),
        "investigate_interests": (
            "Research the interests of the person described below. "
            "Use websearch to find information about their hobbies, sports, "
            "music preferences, volunteer work, side projects, or any "
            "personal interests mentioned online (LinkedIn, Twitter, "
            "personal websites, news articles, conference talks, etc.).\n\n"
            "If highlights are insufficient, follow up with webfetch on "
            "promising URLs.\n\n"
            "Return ONLY the answer in this exact format, with no markdown, "
            "no symbols, no numbers, no line breaks:\n"
            "cooking, hiking, photography, jazz, open source\n\n"
            "Rules:\n"
            "- One line only\n"
            "- Each interest is a single word or short phrase (2-3 words max)\n"
            "- Separate interests with a comma and a space\n"
            "- No punctuation, no symbols, no markdown\n"
            "- No introductory text, no explanations\n"
            "- No XML, HTML, DSML, or any markup of any kind\n"
            "- No tool call syntax, no tags, no brackets\n"
            "- If you cannot find any interests, return: none"
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
