import queue
import threading

_MAX_BATCH = 15


class EventAggregator:
    def __init__(self, interval=300):
        self._queue = queue.Queue()
        self._running = False
        self._timer = None
        self._root = None
        self._callback = None
        self._interval = interval

    def submit(self, event):
        self._queue.put(event)

    def start(self, root, callback, interval=300):
        self._root = root
        self._callback = callback
        self._interval = interval
        self._running = True
        self._schedule()

    def stop(self):
        self._running = False
        if self._timer:
            try:
                self._root.after_cancel(self._timer)
            except Exception:
                pass
            self._timer = None

    def _schedule(self):
        if not self._running:
            return
        self._timer = self._root.after(self._interval, self._flush)

    def _flush(self):
        self._timer = None
        batch = []
        for _ in range(_MAX_BATCH):
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch and self._callback:
            self._callback(batch)
        if self._running:
            remaining = self._queue.qsize()
            if remaining > 0:
                self._timer = self._root.after(10, self._flush)
            else:
                self._schedule()


_event_bus = EventAggregator()


def submit(event):
    _event_bus.submit(event)


def start(root, callback, interval=300):
    _event_bus.start(root, callback, interval)


def stop():
    _event_bus.stop()
