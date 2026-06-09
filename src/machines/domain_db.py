import os
import re
import sqlite3
from datetime import datetime


_DB_DIR = None


def _init_db_dir():
    global _DB_DIR
    if _DB_DIR is None:
        proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _DB_DIR = os.path.join(proj, "databases")
        os.makedirs(_DB_DIR, exist_ok=True)


def _sanitize(domain):
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", domain)


def _get_path(domain):
    _init_db_dir()
    safe = _sanitize(domain)
    return os.path.join(_DB_DIR, f"dom_{safe}.dbs")


def init_or_update(domain, machine_id, machine_ip, source=""):
    _init_db_dir()
    path = _get_path(domain)
    now = datetime.now().isoformat()
    exists = os.path.isfile(path)
    try:
        with sqlite3.connect(path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS domain_info (
                    domain TEXT,
                    first_seen TEXT,
                    last_seen TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS domain_machines (
                    machine_id INTEGER,
                    machine_ip TEXT,
                    source TEXT,
                    discovered_at TEXT
                )
            """)
            if not exists:
                conn.execute(
                    "INSERT INTO domain_info VALUES (?, ?, ?)",
                    (domain, now, now),
                )
            else:
                conn.execute(
                    "UPDATE domain_info SET last_seen = ? WHERE domain = ?",
                    (now, domain),
                )
            conn.execute(
                "INSERT OR REPLACE INTO domain_machines VALUES (?, ?, ?, ?)",
                (machine_id, machine_ip, source, now),
            )
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def load_domain_info(domain):
    _init_db_dir()
    path = _get_path(domain)
    if not os.path.isfile(path):
        return None
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT domain, first_seen, last_seen FROM domain_info"
            ).fetchone()
            if row:
                return {"domain": row[0], "first_seen": row[1], "last_seen": row[2]}
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        pass
    return None


def load_domain_machines(domain):
    _init_db_dir()
    path = _get_path(domain)
    if not os.path.isfile(path):
        return []
    try:
        with sqlite3.connect(path) as conn:
            rows = conn.execute(
                "SELECT machine_id, machine_ip, source, discovered_at FROM domain_machines ORDER BY discovered_at"
            ).fetchall()
            return [{"machine_id": r[0], "machine_ip": r[1], "source": r[2], "discovered_at": r[3]} for r in rows]
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return []


def exists(domain):
    _init_db_dir()
    return os.path.isfile(_get_path(domain))


def list_all():
    _init_db_dir()
    result = []
    for fname in os.listdir(_DB_DIR):
        if fname.startswith("dom_") and fname.endswith(".dbs"):
            result.append(fname[4:-4])
    return result


def delete_all():
    _init_db_dir()
    for fname in os.listdir(_DB_DIR):
        if fname.startswith("dom_") and fname.endswith(".dbs"):
            try:
                os.remove(os.path.join(_DB_DIR, fname))
            except (PermissionError, OSError):
                pass
