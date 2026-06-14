import os
import socket
import threading
import time as _time
from datetime import datetime


# --- debug logging -----------------------------------------------------------
_proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DBG_FILE = os.path.join(_proj_root, "databases", "debugging_logs")
_DBG_LOCK = threading.Lock()


def _dbg(msg):
    line = f"{_time.strftime('%H:%M:%S')}  {msg}\n"
    try:
        with _DBG_LOCK:
            os.makedirs(os.path.dirname(_DBG_FILE), exist_ok=True)
            with open(_DBG_FILE, "a") as f:
                f.write(line)
    except (PermissionError, OSError):
        pass
# ---------------------------------------------------------------------------

_id_counter = 0
_lock = threading.Lock()
_sessions = {}


def _next_id():
    global _id_counter
    _id_counter += 1
    return _id_counter


def add_session(ip, port, listener_port):
    sid = _next_id()
    session = {
        "id": sid,
        "ip": ip,
        "source_port": port,
        "listener_port": listener_port,
        "connected_at": datetime.now(),
        "last_active": datetime.now(),
        "status": "connected",
        "type": "Revershell",
        "buffer": [],
        "socket": None,
        "active": True,
    }
    with _lock:
        _sessions[sid] = session
    _dbg(f"[shell-db] session #{sid} added ({ip}:{port})")
    return session


def set_socket(sid, sock):
    s = get_session(sid)
    if s:
        s["socket"] = sock


def set_status(sid, status):
    s = get_session(sid)
    if s:
        _dbg(f"[shell-db] session #{sid} status -> {status}")
        s["status"] = status


def set_os(sid, shell_os):
    s = get_session(sid)
    if s:
        s["os"] = shell_os
        if shell_os == "windows":
            s["type"] = "Revershell (windows)"
        else:
            s["type"] = "Revershell (unix)"


def append_output(sid, data):
    s = get_session(sid)
    if s:
        s["last_active"] = datetime.now()
        if isinstance(data, bytes):
            try:
                data = data.decode(errors="replace")
            except Exception:
                data = repr(data)
        data = data.replace("\r\n", "\n").replace("\r", "\n")
        s["buffer"].append(data)


def drain_output(sid):
    s = get_session(sid)
    if not s:
        return ""
    buf = s["buffer"]
    if not buf:
        return ""
    result = "".join(buf)
    s["buffer"] = []
    return result


def get_session(sid):
    with _lock:
        return _sessions.get(sid)


def get_all():
    with _lock:
        return sorted(_sessions.values(), key=lambda s: s["id"], reverse=True)


def get_count():
    with _lock:
        return len(_sessions)


def close_session(sid):
    _dbg(f"[shell-db] closing session #{sid}")
    s = get_session(sid)
    if s:
        s["active"] = False
        sock = s.get("socket")
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
                _dbg(f"[shell-db] session #{sid} socket shutdown")
            except Exception:
                pass
            try:
                sock.close()
                _dbg(f"[shell-db] session #{sid} socket closed")
            except Exception:
                pass
        with _lock:
            _sessions.pop(sid, None)
        _dbg(f"[shell-db] session #{sid} removed")
