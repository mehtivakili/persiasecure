"""
Cross-camera batching (Phase AI-1).

On a GPU, one forward pass over N frames is far cheaper than N passes, so many
cameras should share a card by batching their frames. This module provides the
two pure, tested pieces:

  * `group(items, max_size)` — chunk pending frames into batches ≤ the GPU's
    comfortable batch size.
  * `BatchCollector` — a tiny thread-safe accumulator: camera workers `add()`
    frames; a batch worker `drain(max_size)` pulls a batch when enough have
    arrived (or a flush timeout elapses) and runs `Detector.infer_batch`.

The threaded scheduler that wires this into the live loop is a deployment-tuning
step (enabled when a single GPU serves many cameras); these primitives make it
correct and testable independent of that wiring.
"""
import threading


def group(items, max_size):
    """Split `items` into consecutive chunks of at most `max_size`."""
    if max_size < 1:
        raise ValueError("max_size must be >= 1")
    return [items[i:i + max_size] for i in range(0, len(items), max_size)]


class BatchCollector:
    """
    Thread-safe FIFO of `(key, frame)` pairs awaiting inference. Camera workers
    `add`; a batch worker `drain` up to `max_size` at a time. `key` lets the
    caller route each result back to the right camera/tracker.
    """

    def __init__(self):
        self._items = []
        self._lock = threading.Lock()
        self._event = threading.Event()

    def add(self, key, frame):
        with self._lock:
            self._items.append((key, frame))
        self._event.set()

    def __len__(self):
        with self._lock:
            return len(self._items)

    def drain(self, max_size):
        """Remove and return up to `max_size` pending items (FIFO)."""
        with self._lock:
            batch = self._items[:max_size]
            self._items = self._items[max_size:]
            if not self._items:
                self._event.clear()
            return batch

    def wait(self, timeout=None):
        """Block until at least one item is available or `timeout` elapses."""
        return self._event.wait(timeout)
