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

def lst_dir() -> Path:
    p = _get_data_home() / "lst"
    p.mkdir(parents=True, exist_ok=True)
    return p

def settings_file() -> Path:
    p = _get_data_home() / "settings.json"
    return p
