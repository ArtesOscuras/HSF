import os
import sqlite3
from datetime import datetime


_DB_PATH = None


def _init_db_path():
    global _DB_PATH
    if _DB_PATH is None:
        proj = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.path.join(proj, "credentials")
        os.makedirs(db_dir, exist_ok=True)
        _DB_PATH = os.path.join(db_dir, "credentials.dbs")


def _migrate_cred_table():
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(credentials)").fetchall()]
            for col in ("domain", "hash_nt", "password_origin", "hash_nt_origin"):
                if col not in cols:
                    conn.execute(f"ALTER TABLE credentials ADD COLUMN {col} TEXT DEFAULT ''")
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        conn = sqlite3.connect(_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                password TEXT,
                domain TEXT,
                hash_nt TEXT,
                password_origin TEXT,
                hash_nt_origin TEXT
            )
        """)


def save_credential(username, password, domain="", hash_nt="", password_origin="", hash_nt_origin=""):
    _init_db_path()
    _migrate_cred_table()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                "INSERT INTO credentials (username, password, domain, hash_nt, password_origin, hash_nt_origin) VALUES (?, ?, ?, ?, ?, ?)",
                (username, password, domain, hash_nt, password_origin, hash_nt_origin),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except (PermissionError, OSError, sqlite3.OperationalError):
        return None


def update_credential(cred_id, username, password, domain="", hash_nt="", password_origin="", hash_nt_origin=""):
    _init_db_path()
    _migrate_cred_table()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                "UPDATE credentials SET username=?, password=?, domain=?, hash_nt=?, password_origin=?, hash_nt_origin=? WHERE id=?",
                (username, password, domain, hash_nt, password_origin, hash_nt_origin, cred_id),
            )
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def load_credentials():
    _init_db_path()
    if not os.path.isfile(_DB_PATH):
        return []
    _migrate_cred_table()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            rows = conn.execute(
                "SELECT id, username, password, domain, hash_nt, password_origin, hash_nt_origin FROM credentials ORDER BY id DESC"
            ).fetchall()
            return [{"id": r[0], "username": r[1], "password": r[2],
                     "domain": r[3], "hash_nt": r[4],
                     "password_origin": r[5], "hash_nt_origin": r[6]} for r in rows]
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return []


def load_credential(cred_id):
    _init_db_path()
    if not os.path.isfile(_DB_PATH):
        return None
    _migrate_cred_table()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            row = conn.execute(
                "SELECT id, username, password, domain, hash_nt, password_origin, hash_nt_origin FROM credentials WHERE id = ?",
                (cred_id,),
            ).fetchone()
            if row:
                return {"id": row[0], "username": row[1], "password": row[2],
                        "domain": row[3], "hash_nt": row[4],
                        "password_origin": row[5], "hash_nt_origin": row[6]}
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        pass
    return None


def delete_credential(cred_id):
    _init_db_path()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("DELETE FROM credentials WHERE id = ?", (cred_id,))
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def save_user(username):
    _init_db_path()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT UNIQUE
                )
            """)
            conn.execute("INSERT OR IGNORE INTO users VALUES (?)", (username,))
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def load_users():
    _init_db_path()
    if not os.path.isfile(_DB_PATH):
        return []
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT UNIQUE
                )
            """)
            rows = conn.execute("SELECT username FROM users ORDER BY username").fetchall()
            return [r[0] for r in rows]
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return []


def delete_user(username):
    _init_db_path()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def save_password(password):
    _init_db_path()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS passwords (
                    password TEXT UNIQUE
                )
            """)
            conn.execute("INSERT OR IGNORE INTO passwords VALUES (?)", (password,))
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def load_passwords():
    _init_db_path()
    if not os.path.isfile(_DB_PATH):
        return []
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS passwords (
                    password TEXT UNIQUE
                )
            """)
            rows = conn.execute("SELECT password FROM passwords ORDER BY password").fetchall()
            return [r[0] for r in rows]
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return []


def delete_password(password):
    _init_db_path()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("DELETE FROM passwords WHERE password = ?", (password,))
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass


def delete_all():
    _init_db_path()
    try:
        if os.path.isfile(_DB_PATH):
            os.remove(_DB_PATH)
    except (PermissionError, OSError):
        pass


def save_hash_entry(hash_type, hash_value, salt="", peper="", hascat_mode="", origin=""):
    _init_db_path()
    now = datetime.now().isoformat()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hashes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    hash TEXT,
                    salt TEXT,
                    peper TEXT,
                    hascat_mode TEXT,
                    origin_obteined TEXT,
                    obtained_date_time TEXT
                )
            """)
            conn.execute(
                "INSERT INTO hashes (type, hash, salt, peper, hascat_mode, origin_obteined, obtained_date_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (hash_type, hash_value, salt, peper, hascat_mode, origin, now),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    except (PermissionError, OSError, sqlite3.OperationalError):
        return None


def load_hashes():
    _init_db_path()
    if not os.path.isfile(_DB_PATH):
        return []
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hashes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    hash TEXT,
                    salt TEXT,
                    peper TEXT,
                    hascat_mode TEXT,
                    origin_obteined TEXT,
                    obtained_date_time TEXT
                )
            """)
            rows = conn.execute(
                "SELECT id, type, hash, salt, peper, hascat_mode, origin_obteined, obtained_date_time FROM hashes ORDER BY id DESC"
            ).fetchall()
            return [{"id": r[0], "type": r[1], "hash": r[2], "salt": r[3],
                     "peper": r[4], "hascat_mode": r[5],
                     "origin_obteined": r[6], "obtained_date_time": r[7]} for r in rows]
    except (sqlite3.DatabaseError, sqlite3.OperationalError):
        return []


def delete_hash_entry(hash_id):
    _init_db_path()
    try:
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute("DELETE FROM hashes WHERE id = ?", (hash_id,))
    except (PermissionError, OSError, sqlite3.OperationalError):
        pass
