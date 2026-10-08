"""Thread-safe, append-only observed events for synthetic local runs."""

import json
import threading
import time
from pathlib import Path

from .wire import canonical


class EvidenceLog:
    def __init__(self, path):
        self.path = Path(path)
        self._stream = self.path.open("w", encoding="utf-8", newline="\n")
        self._lock = threading.Condition()
        self._start = time.monotonic()
        self._events = []

    def emit(self, layer, agent, event, **fields):
        with self._lock:
            record = {"seq": len(self._events) + 1,
                      "elapsed_ms": round((time.monotonic() - self._start) * 1000, 3),
                      "layer": layer, "agent": agent, "event": event, **fields}
            # Freeze mutable caller dictionaries before a concurrent update.
            record = json.loads(canonical(record))
            self._stream.write(canonical(record) + "\n")
            self._stream.flush()
            self._events.append(record)
            self._lock.notify_all()
            return record["seq"]

    def snapshot(self):
        with self._lock:
            return json.loads(canonical(self._events))

    def wait_for(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        with self._lock:
            while True:
                match = next((event for event in self._events if predicate(event)), None)
                if match is not None:
                    return json.loads(canonical(match))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Expected evidence event was not observed before the bound")
                self._lock.wait(remaining)

    def close(self):
        self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
