import os
import queue
import threading
import time
from ftplib import FTP, error_perm
from . import shell_db

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


class FTPConnectionThread:
    def __init__(self, host, port, user, password, sid):
        self._host = host
        self._port = port or 21
        self._user = user
        self._password = password
        self._sid = sid
        self._queue = queue.Queue()
        self._running = True
        self._ftp = None
        self._awaiting_pass = False

    @property
    def queue(self):
        return self._queue

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._running = False
        self._queue.put(None)
        if self._ftp:
            try:
                self._ftp.quit()
            except Exception:
                pass

    def _run(self):
        ftp = FTP()
        self._ftp = ftp
        try:
            ftp.connect(self._host, self._port, timeout=10)
            shell_db.append_output(self._sid, f"Connected to {self._host}:{self._port}\n")
            _dbg(f"[ftp-shell #{self._sid}] connected")
        except Exception as e:
            shell_db.append_output(self._sid, f"Connection failed: {e}\n")
            shell_db.set_status(self._sid, "disconnected")
            return

        if self._user:
            if self._password:
                try:
                    ftp.login(self._user, self._password)
                    shell_db.append_output(self._sid, f"Logged in as {self._user}\n")
                    _dbg(f"[ftp-shell #{self._sid}] logged in as {self._user}")
                except error_perm as e:
                    shell_db.append_output(self._sid, f"Login failed: {e}\n")
                    shell_db.set_status(self._sid, "disconnected")
                    return
            else:
                try:
                    resp = ftp.sendcmd(f"USER {self._user}")
                    shell_db.append_output(self._sid, f"{resp}\n")
                    self._awaiting_pass = True
                    _dbg(f"[ftp-shell #{self._sid}] sent USER {self._user}, awaiting PASS")
                except error_perm as e:
                    shell_db.append_output(self._sid, f"USER failed: {e}\n")
                    shell_db.set_status(self._sid, "disconnected")
                    return

        shell_db.append_output(self._sid, "Type 'help' for available commands.\n")

        while self._running:
            try:
                raw = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if raw is None:
                break

            cmd = raw.strip()
            if not cmd:
                continue
            if self._awaiting_pass:
                self._awaiting_pass = False
                raw = f"pass {cmd}"
                cmd = raw.strip()

            if cmd == "quit" or cmd == "exit" or cmd == "bye":
                shell_db.append_output(self._sid, f"{cmd}\nGoodbye.\n")
                break

            try:
                output = self._execute(cmd)
                if output:
                    shell_db.append_output(self._sid, output.rstrip("\n") + "\n")
                else:
                    shell_db.append_output(self._sid, "(no output)\n")
            except Exception as e:
                shell_db.append_output(self._sid, f"Error: {e}\n")

        try:
            ftp.quit()
        except Exception:
            pass
        shell_db.append_output(self._sid, "Connection closed.\n")
        shell_db.set_status(self._sid, "disconnected")

    def _execute(self, cmd):
        parts = cmd.split()
        verb = parts[0].lower()
        args = parts[1:]

        if verb == "ls" or verb == "dir":
            buf = []
            try:
                def callback(line):
                    buf.append(line)
                if args:
                    self._ftp.retrlines(f"LIST {' '.join(args)}", callback)
                else:
                    self._ftp.retrlines("LIST", callback)
            except error_perm as e:
                return f"Permission error: {e}"
            return "\n".join(buf) if buf else "(empty)"

        elif verb == "lls":
            try:
                files = os.listdir(" ".join(args) if args else ".")
                return "\n".join(files) if files else "(empty)"
            except Exception as e:
                return f"Error: {e}"

        elif verb == "cd":
            self._ftp.cwd(" ".join(args))
            return f"Directory changed to {self._ftp.pwd()}"

        elif verb == "pwd":
            return self._ftp.pwd()

        elif verb == "get":
            if not args:
                return "Usage: get <remote_file> [local_name]"
            remote = args[0]
            local = args[1] if len(args) > 1 else remote
            try:
                with open(local, "wb") as f:
                    self._ftp.retrbinary(f"RETR {remote}", f.write)
                return f"Downloaded {remote} -> {local}"
            except Exception as e:
                return f"Download failed: {e}"

        elif verb == "put":
            if not args:
                return "Usage: put <local_file> [remote_name]"
            local = args[0]
            remote = args[1] if len(args) > 1 else local
            if not os.path.isfile(local):
                return f"Local file not found: {local}"
            try:
                with open(local, "rb") as f:
                    self._ftp.storbinary(f"STOR {remote}", f)
                return f"Uploaded {local} -> {remote}"
            except Exception as e:
                return f"Upload failed: {e}"

        elif verb == "delete" or verb == "del":
            if not args:
                return "Usage: delete <remote_file>"
            self._ftp.delete(args[0])
            return f"Deleted {args[0]}"

        elif verb == "mkdir":
            if not args:
                return "Usage: mkdir <remote_dir>"
            self._ftp.mkd(" ".join(args))
            return f"Created directory"

        elif verb == "rmdir":
            if not args:
                return "Usage: rmdir <remote_dir>"
            self._ftp.rmd(" ".join(args))
            return f"Removed directory"

        elif verb == "rename":
            if len(args) < 2:
                return "Usage: rename <from> <to>"
            self._ftp.rename(args[0], args[1])
            return f"Renamed {args[0]} -> {args[1]}"

        elif verb == "size":
            if not args:
                return "Usage: size <remote_file>"
            try:
                s = self._ftp.size(args[0])
                return f"{args[0]}: {s} bytes"
            except Exception as e:
                return f"Error: {e}"

        elif verb == "chmod":
            if len(args) < 2:
                return "Usage: chmod <mode> <remote_file>"
            try:
                self._ftp.voidcmd(f"SITE CHMOD {args[0]} {args[1]}")
                return f"Permissions changed"
            except error_perm:
                return "CHMOD not supported by server"

        elif verb == "user":
            if not args:
                return "Usage: user <username>"
            try:
                resp = self._ftp.sendcmd(f"USER {args[0]}")
                if resp.startswith("3"):
                    self._awaiting_pass = True
                return resp
            except error_perm as e:
                return f"Error: {e}"

        elif verb == "pass":
            if not args:
                return "Usage: pass <password>"
            try:
                resp = self._ftp.sendcmd(f"PASS {args[0]}")
                if resp.startswith("2") or resp.startswith("3"):
                    self._user = args[0]
                return resp
            except error_perm as e:
                return f"Error: {e}"

        elif verb == "help":
            return ("Available commands:\n"
                    "  ls/dir     List remote directory\n"
                    "  lls        List local directory\n"
                    "  cd         Change remote directory\n"
                    "  pwd        Print working directory\n"
                    "  get        Download file\n"
                    "  put        Upload file\n"
                    "  delete     Delete remote file\n"
                    "  mkdir      Create remote directory\n"
                    "  rmdir      Remove remote directory\n"
                    "  rename     Rename remote file\n"
                    "  user       Send username to server\n"
                    "  pass       Send password to server\n"
                    "  size       Get file size\n"
                    "  chmod      Change permissions\n"
                    "  quit/exit  Close connection")

        else:
            try:
                resp = self._ftp.sendcmd(cmd.upper())
                return str(resp) if resp else "OK"
            except error_perm as e:
                return f"FTP error: {e}"
