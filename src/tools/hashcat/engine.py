"""Hashcat engine — wraps the hashcat binary for background cracking."""
import re
import subprocess
import threading
import time

from src.resolve_binary import resolve


_PROGRESS_RE = re.compile(r"Progress\.+:\s+(\d+)/(\d+)")
_RECOVERED_RE = re.compile(r"Recovered\.+:\s+(\d+)/(\d+).*?Digests")


class HashcatEngine:
    def __init__(self, mode, hash_value, wordlist, rules_file=None,
                 backend=None,
                 on_output=None, on_cracked=None, on_done=None,
                 on_progress=None):
        self._mode = str(mode)
        self._hash_value = hash_value
        self._wordlist = wordlist
        self._rules_file = rules_file
        self._backend = backend
        self._on_output = on_output
        self._on_cracked = on_cracked
        self._on_done = on_done
        self._on_progress = on_progress
        self._proc = None
        self._stop_flag = threading.Event()
        self._progress_done = 0
        self._progress_total = 0
        self._progress_recovered = 0

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop_flag.set()
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    @staticmethod
    def is_available():
        return resolve("hashcat") is not None

    @staticmethod
    def detect_hardware():
        binary = resolve("hashcat")
        if not binary:
            return {"cpu": True, "gpu": True}

        try:
            r = subprocess.run(
                [binary, "-I"],
                capture_output=True, text=True, timeout=10,
            )
            output = r.stdout + r.stderr
            has_cpu = "Type...........: CPU" in output
            has_gpu = "Type...........: GPU" in output
            return {"cpu": has_cpu, "gpu": has_gpu}
        except (OSError, subprocess.TimeoutExpired):
            return {"cpu": True, "gpu": True}

    def _run(self):
        binary = resolve("hashcat")
        if not binary:
            if self._on_output:
                self._on_output("hashcat binary not found in PATH.\n", "error")
            self._finish(None)
            return

        cmd = [
            binary,
            "-m", self._mode,
            self._hash_value,
            self._wordlist,
            "--quiet",
            "--status",
            "--status-timer=1",
            "--potfile-disable",
        ]
        if self._backend:
            cmd.extend(["-D", self._backend])
        if self._rules_file:
            cmd.extend(["-r", self._rules_file])

        self._emit(f"\n[>] hashcat -m {self._mode} '{self._hash_value[:40]}...' {self._wordlist}\n", "info")

        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            if self._on_output:
                self._on_output(f"Failed to start hashcat: {e}\n", "error")
            self._finish(None)
            return

        cracked = []
        for line in self._proc.stdout:
            if self._stop_flag.is_set():
                self._proc.terminate()
                break
            line = line.rstrip("\n")
            if not line:
                continue
            self._emit(f"  {line}\n")
            self._parse_progress(line)
            if _is_cracked_line(line, self._hash_value):
                plain = line.split(":", 1)[1]
                if plain and len(plain) < 200:
                    cracked.append(line)

        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()

        self._finish(cracked)

    def _emit(self, text, color=None):
        if self._on_output:
            self._on_output(text, color)

    def _parse_progress(self, line):
        m = _PROGRESS_RE.search(line)
        if m:
            self._progress_done = int(m.group(1))
            self._progress_total = int(m.group(2))
            if self._on_progress:
                self._on_progress(self._progress_done, self._progress_total,
                                  self._progress_recovered)
            return
        m = _RECOVERED_RE.search(line)
        if m:
            self._progress_recovered = int(m.group(1))

    def _finish(self, cracked):
        if self._on_progress and self._progress_total > 0:
            self._on_progress(self._progress_total, self._progress_total,
                              self._progress_recovered)
        if cracked:
            for c in cracked:
                if self._on_cracked:
                    plain = c.split(":", 1)[-1] if ":" in c else c
                    self._on_cracked(self._hash_value, plain)
        if self._on_done:
            self._on_done(cracked or [])


_STATUS_RE = re.compile(r"\.{3,}:")  # status lines have "..........:" before value


def _is_cracked_line(line, hash_val):
    if not line:
        return False
    if _STATUS_RE.search(line):
        return False
    if line.startswith(hash_val + ":"):
        return True
    if re.match(r"^[a-fA-F0-9]{16,}:", line):
        return True
    return False
