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
        "system": (
            "You are an AI assistant operating within HSF, a penetration testing program. "
            "Your objective is to assist the user with any tasks they request. "
            "Only perform the specific functions the user asks for.\n\n"
            "You operate in two modes. Each request will tell you which mode you are in:\n"
            "- AGENT mode: you may call tools freely when they would help.\n"
            "- CONSULTOR mode: you may NOT call tools. Only provide advice, analysis, and "
            "conversation. Never invoke tools in consultor mode.\n\n"
            "When in AGENT mode, available tool categories:\n"
            "- Data: check_machine, check_domain, check_inventory, check_shells, "
            "check_evidences, check_fuzz_results (query inventory); add/delete users, "
            "machines, domains, credentials, hashes, passwords, people.\n"
            "- Network: list_interfaces, scan_interface, scan_ip, stop_scan, "
            "tcp_scan/udp_scan (return common ports immediately then continue full "
            "scan in background — results via check_machine), ping, nslookup, "
            "port_inspector, bannergrab, nmap.\n"
            "- Web: websearch (search internet), webfetch (read URLs; auto-saves "
            "visited URL paths to the directories table for known machines/domains).\n"
            "- Attack: hashcat_crack, bruteforce_start, fuzz_start (results saved "
            "to agent_fuzzing table; use check_fuzz_results to retrieve).\n"
            "- Wordlists: dicma_generate_users, dicma_generate_passwords, "
            "dicma_generate_rules, dicma_find_related.\n"
            "- Infrastructure: start/stop listeners, list/delete dictionaries/rules/files, "
            "shell operations, SSH/SFTP/FTP/WinRM connections.\n\n"
            "Prefer websearch for general research. Use webfetch for specific pages. "
            "Fast tools (ping, nslookup, port_inspector, bannergrab, scan_ip) return "
            "results immediately. Slower scans (tcp_scan full, udp_scan full, "
            "scan_interface) run in background — check results later via check_machine "
            "or check_fuzz_results. Always check the inventory context before asking "
            "the user. Be concise and direct."
        ),
        "evidence_analysis": (
            "This evidence is part of a web browsing session. "
            "You need to analyze it. You have more details in the "
            "'For LLM analysis.md' file in the same directory."
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
        if "system" not in data.get("prompts", {}):
            data.setdefault("prompts", {})["system"] = data.pop("system_prompt")
        else:
            data.pop("system_prompt")
    prompts = data.get("prompts", {})
    if "consultor" in prompts and "system" not in prompts:
        prompts["system"] = prompts.pop("consultor")
    if "agent" in prompts:
        prompts.pop("agent", None)
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
