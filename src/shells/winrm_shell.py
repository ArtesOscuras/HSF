import queue
import threading
import time
from . import shell_db
from .winrmexec import (
    SPNEGOTransport, NTCredential, Runspace,
)


class WinRMConnectionThread:
    def __init__(self, host, port, user, password, domain="", on_connected=None, on_error=None):
        self._host = host
        self._port = port or 5985
        self._user = user
        self._password = password
        self._domain = domain
        self._on_connected = on_connected
        self._on_error = on_error
        self._sid = None
        self._queue = queue.Queue()
        self._running = True
        self._runspace = None

    @property
    def queue(self):
        return self._queue

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self._running = False
        self._queue.put(None)
        self._close()

    def _close(self):
        if self._runspace:
            try:
                self._runspace.__exit__(None, None, None)
            except Exception:
                pass

    def _run(self):
        try:
            url = f"http://{self._host}:{self._port}/wsman"
            creds = NTCredential(self._domain or ".", self._user, self._password)
            transport = SPNEGOTransport(url, creds)
            runspace = Runspace(transport, timeout=10)
            runspace.__enter__()
            self._runspace = runspace
        except Exception as e:
            if self._on_error:
                self._on_error(f"Connection failed: {e}")
            return

        session = shell_db.add_session(self._host, self._port, 0)
        session["type"] = "WINRM"
        session["cmd_queue"] = self._queue
        session["winrm_runspace"] = runspace
        self._sid = session["id"]

        shell_db.append_output(self._sid, f"Connected to {self._host}:{self._port}\n")
        shell_db.append_output(self._sid, f"Logged in as {self._user}\n")
        shell_db.append_output(self._sid, "Type 'exit' to close.\n")

        if self._on_connected:
            self._on_connected(self._sid)

        try:
            for out in runspace.run_command("(Get-Location).Path"):
                if "stdout" in out:
                    cwd = out["stdout"].strip()
                    if cwd:
                        session["winrm_cwd"] = cwd
        except Exception:
            pass

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

            if cmd == "quit" or cmd == "exit" or cmd == "bye":
                shell_db.append_output(self._sid, "Goodbye.\n")
                break

            try:
                for output in runspace.run_command(cmd):
                    if "stdout" in output:
                        text = output["stdout"]
                        if not text.endswith("\n"):
                            text += "\n"
                        shell_db.append_output(self._sid, text)
                    elif "error" in output:
                        shell_db.append_output(self._sid, f"Error: {output['error']}\n")
            except Exception:
                pass

            cwd_ok = True
            try:
                for out in runspace.run_command("(Get-Location).Path"):
                    if "stdout" in out:
                        cwd = out["stdout"].strip()
                        if cwd:
                            s = shell_db.get_session(self._sid)
                            if s:
                                s["winrm_cwd"] = cwd
            except Exception:
                cwd_ok = False

            if not cwd_ok:
                try:
                    runspace.__exit__(None, None, None)
                    transport = SPNEGOTransport(
                        f"http://{self._host}:{self._port}/wsman",
                        NTCredential(self._domain or ".", self._user, self._password),
                    )
                    runspace = Runspace(transport, timeout=10)
                    runspace.__enter__()
                    self._runspace = runspace
                    session["winrm_runspace"] = runspace
                except Exception:
                    shell_db.append_output(self._sid, "Connection lost. Type exit and reconnect.\n")
                    break

        runspace.__exit__(None, None, None)
        shell_db.append_output(self._sid, "Connection closed.\n")
        shell_db.set_status(self._sid, "disconnected")
