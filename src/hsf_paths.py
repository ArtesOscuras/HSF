import os
from pathlib import Path
from importlib.resources import files

_PKG = files("src")

def fonts_dir() -> Path:
    return _PKG / "fonts"

def icons_dir() -> Path:
    return _PKG / "icons"

def hashcat_db() -> Path:
    return _PKG / "data" / "hashcat.dbs"

def _get_data_home() -> Path:
    override = os.environ.get("HSF_HOME")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "hsf"

def databases_dir() -> Path:
    p = _get_data_home() / "databases"
    p.mkdir(parents=True, exist_ok=True)
    return p

def credentials_dir() -> Path:
    p = _get_data_home() / "credentials"
    p.mkdir(parents=True, exist_ok=True)
    return p

def evidence_dir() -> Path:
    p = _get_data_home() / "evidence"
    p.mkdir(parents=True, exist_ok=True)
    return p

def chrome_profile_dir() -> Path:
    p = _get_data_home() / "chrome_profile"
    p.mkdir(parents=True, exist_ok=True)
    return p

def antibot_profile_dir() -> Path:
    p = _get_data_home() / "antibot_profile"
    p.mkdir(parents=True, exist_ok=True)
    return p

def lst_dir() -> Path:
    p = _get_data_home() / "lst"
    p.mkdir(parents=True, exist_ok=True)
    if not any(p.iterdir()):
        src = _PKG / "lst"
        if src.is_dir():
            for f in src.iterdir():
                if f.is_file():
                    _dst = p / f.name
                    if not _dst.exists():
                        _dst.write_bytes(f.read_bytes())
    return p

def rules_dir() -> Path:
    p = _get_data_home() / "rules"
    p.mkdir(parents=True, exist_ok=True)
    if not any(p.iterdir()):
        src = _PKG / "rules"
        if src.is_dir():
            for f in src.iterdir():
                if f.is_file():
                    _dst = p / f.name
                    if not _dst.exists():
                        _dst.write_bytes(f.read_bytes())
    return p

def pocs_dir() -> Path:
    p = _get_data_home() / "pocs"
    p.mkdir(parents=True, exist_ok=True)
    return p

def reports_dir() -> Path:
    p = _get_data_home() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p

def cache_dir() -> Path:
    p = _get_data_home() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p

def models_catalog_file() -> Path:
    return databases_dir() / "models_catalog.json"

def settings_file() -> Path:
    p = _get_data_home() / "settings.json"
    return p

def session_file() -> Path:
    return _get_data_home() / "session.json"

def logs_dir() -> Path:
    return _PKG / "logs"

def runtime_logs_dir() -> Path:
    p = _get_data_home() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p
