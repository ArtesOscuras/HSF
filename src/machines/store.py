import json
import os
import sqlite3
import threading
import time as _time
from datetime import datetime


_DB_FILE = None
_AUTOSAVE_INTERVAL = 10
_autosave_running = False
_autosave_thread = None
_save_lock = threading.Lock()


def _init_db_path():
    global _DB_FILE
    if _DB_FILE is None:
        proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.path.join(proj, "databases")
        os.makedirs(db_dir, exist_ok=True)
        _DB_FILE = os.path.join(db_dir, "machines.dbs")


class Machine:
    def __init__(self, ip, hostname="", mac="", method=""):
        self.ip = ip
        self.hostname = hostname
        self.mac = mac
        self.device_type = ""
        self.model = ""
        self.methods = {method} if method else set()
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()

    def update(self, hostname="", mac="", method=""):
        if hostname and not self.hostname:
            self.hostname = hostname
        if mac and not self.mac:
            self.mac = mac
        if method:
            self.methods.add(method)
        self.last_seen = datetime.now()

    def to_dict(self):
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "mac": self.mac,
            "device_type": self.device_type,
            "model": self.model,
            "methods": sorted(self.methods),
            "first_seen": self.first_seen.strftime("%H:%M:%S"),
            "last_seen": self.last_seen.strftime("%H:%M:%S"),
        }


class MachineStore:
    def __init__(self):
        self._machines = {}

    def add_or_update(self, ip, hostname="", mac="", method=""):
        if ip in self._machines:
            self._machines[ip].update(hostname=hostname, mac=mac, method=method)
        else:
            self._machines[ip] = Machine(ip, hostname=hostname, mac=mac, method=method)
        return self._machines[ip]

    def get(self, ip):
        return self._machines.get(ip)

    def get_all(self):
        return list(self._machines.values())

    def get_all_sorted(self):
        return sorted(self._machines.values(), key=lambda m: m.first_seen)

    def count(self):
        return len(self._machines)

    def clear(self):
        self._machines.clear()

    def save(self):
        _init_db_path()
        try:
            with _save_lock, sqlite3.connect(_DB_FILE) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS machines (
                        ip TEXT PRIMARY KEY,
                        hostname TEXT,
                        mac TEXT,
                        device_type TEXT,
                        model TEXT,
                        methods TEXT,
                        first_seen TEXT,
                        last_seen TEXT
                    )
                """)
                try:
                    conn.execute("ALTER TABLE machines ADD COLUMN model TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass
                for m in self._machines.values():
                    conn.execute(
                        "INSERT OR REPLACE INTO machines VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            m.ip,
                            m.hostname,
                            m.mac,
                            m.device_type,
                            m.model,
                            json.dumps(sorted(m.methods)),
                            m.first_seen.isoformat(),
                            m.last_seen.isoformat(),
                        ),
                    )
        except (PermissionError, OSError, sqlite3.OperationalError):
            pass

    def load(self):
        _init_db_path()
        if not os.path.isfile(_DB_FILE):
            return
        try:
            with sqlite3.connect(_DB_FILE) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS machines (
                        ip TEXT PRIMARY KEY,
                        hostname TEXT,
                        mac TEXT,
                        device_type TEXT,
                        model TEXT,
                        methods TEXT,
                        first_seen TEXT,
                        last_seen TEXT
                    )
                """)
                try:
                    conn.execute("ALTER TABLE machines ADD COLUMN model TEXT DEFAULT ''")
                except sqlite3.OperationalError:
                    pass
                rows = conn.execute(
                    "SELECT ip, hostname, mac, device_type, model, methods, first_seen, last_seen FROM machines"
                ).fetchall()
        except (sqlite3.DatabaseError, sqlite3.OperationalError):
            return

        for row in rows:
            ip, hostname, mac, device_type, model, methods_json, first_seen, last_seen = row
            m = Machine(ip, hostname=hostname, mac=mac)
            m.device_type = device_type
            m.model = model or ""
            try:
                m.methods = set(json.loads(methods_json))
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                m.first_seen = datetime.fromisoformat(first_seen)
            except (ValueError, TypeError):
                pass
            try:
                m.last_seen = datetime.fromisoformat(last_seen)
            except (ValueError, TypeError):
                pass
            self._machines[ip] = m


def start_autosave(store_instance):
    global _autosave_running, _autosave_thread, _store_ref
    _store_ref = store_instance
    if _autosave_running:
        return
    _autosave_running = True
    _autosave_thread = threading.Thread(target=_autosave_loop, daemon=True)
    _autosave_thread.start()


def stop_autosave():
    global _autosave_running
    _autosave_running = False


def _autosave_loop():
    while _autosave_running:
        _time.sleep(_AUTOSAVE_INTERVAL)
        if _autosave_running:
            _store_ref.save()
