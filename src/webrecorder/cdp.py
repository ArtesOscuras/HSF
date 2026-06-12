import json
import threading

try:
    from websocket import create_connection
    from websocket import WebSocketTimeoutException, WebSocketConnectionClosedException
except ImportError:
    create_connection = None
    WebSocketTimeoutException = OSError
    WebSocketConnectionClosedException = OSError


class CDPClient:
    def __init__(self, ws_url):
        if create_connection is None:
            raise RuntimeError("websocket-client not installed")
        self._ws = create_connection(ws_url, timeout=10)
        self._ws.settimeout(3)
        self._msg_id = 0
        self._lock = threading.Lock()

    def send(self, method, params=None):
        with self._lock:
            self._msg_id += 1
            msg = {"id": self._msg_id, "method": method}
            if params:
                msg["params"] = params
            self._ws.send(json.dumps(msg))
            return self._msg_id

    def recv(self):
        data = self._ws.recv()
        if data:
            return json.loads(data)
        return None

    def call(self, method, params=None):
        msg_id = self.send(method, params)
        while True:
            resp = self.recv()
            if resp is None:
                return None
            if resp.get("id") == msg_id:
                return resp.get("result")
            if "error" in resp:
                return None

    def events(self):
        while True:
            try:
                data = self._ws.recv()
                if data is None:
                    break
                msg = json.loads(data)
                if "id" not in msg:
                    yield msg
            except WebSocketTimeoutException:
                continue
            except WebSocketConnectionClosedException:
                break
            except Exception:
                break

    def close(self):
        self._ws.close()
