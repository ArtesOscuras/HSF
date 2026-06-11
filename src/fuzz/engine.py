import ssl
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from .wordlist import load_wordlist

TIMEOUT = 5
MAX_WORKERS = 20
SHOW_CODES = {200, 301, 302, 307, 401, 403}
USER_AGENT = "HSF/1.0"

_ssl_context = ssl.create_default_context()
_ssl_context.check_hostname = False
_ssl_context.verify_mode = ssl.CERT_NONE


class FuzzEngine:
    def __init__(self, target, wordlist_path, method, target_ip=None, on_result=None, workers=None, on_progress=None):
        self._target = target
        self._wordlist_path = wordlist_path
        self._method = method
        self._target_ip = target_ip
        self._on_result = on_result
        self._on_progress = on_progress
        self._stop_flag = threading.Event()
        self._executor = None
        self._workers = workers or MAX_WORKERS

    def start(self):
        self._stop_flag.clear()
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop_flag.set()

    def _emit(self, text, color=None):
        if self._on_result:
            self._on_result(text, color)

    def _run(self):
        words = load_wordlist(self._wordlist_path)
        total = len(words)
        self._emit(f"\n[*] Loaded {total} words\n")

        self._executor = ThreadPoolExecutor(max_workers=self._workers)
        futures = {}
        for word in words:
            if self._stop_flag.is_set():
                break
            fut = self._executor.submit(self._do_request, word)
            futures[fut] = word

        done = 0
        found = 0
        for fut in as_completed(futures):
            if self._stop_flag.is_set():
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._emit("\n[*] Stopped.\n", "success")
                return
            word = futures[fut]
            done += 1
            try:
                status, length = fut.result()
                if status and status in SHOW_CODES:
                    found += 1
                    self._emit(f"  [{status}] {word:<40} {length:>6}B\n", "success")
            except Exception:
                pass
            if done % 50 == 0 and self._on_progress:
                self._on_progress(done, total, found)

        self._executor.shutdown(wait=False)
        if self._on_progress:
            self._on_progress(total, total, found)
        self._emit(f"\n[+] Done. {found} results from {total} requests.\n", "success")

    def _do_request(self, word):
        req = self._build_request(word)
        try:
            resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context)
            body = resp.read(10240)
            return resp.status, len(body)
        except urllib.request.HTTPError as e:
            body = e.read(10240)
            return e.code, len(body)
        except Exception:
            return None, 0

    def _build_request(self, word):
        method = self._method
        target = self._target
        if method == "directory":
            url = f"http://{target}/{word}/"
            return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        elif method == "vhost":
            ip = self._target_ip or target
            req = urllib.request.Request(
                f"http://{ip}/",
                headers={"User-Agent": USER_AGENT, "Host": f"{word}.{target}"},
            )
            return req
        else:
            url = f"http://{word}.{target}/"
            return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
