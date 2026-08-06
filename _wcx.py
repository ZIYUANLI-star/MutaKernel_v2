"""Resilient wrapper around _remote for the WC-1 audit takeover.

Session() keeps one SSH client alive and transparently rebuilds it whenever a
channel dies, so a transient drop costs a reconnect instead of aborting the
run.  Connect failures only propagate after the whole backoff ladder is spent.
"""
from __future__ import annotations

import time

import _remote

DELAYS = [20, 40, 60, 90, 120]


def connect_retry(attempts: int = 5, label: str = ""):
    last = None
    for i in range(attempts):
        try:
            c = _remote.connect()
            if i:
                print("[wcx] %sconnected on attempt %d" % (label, i + 1), flush=True)
            return c
        except Exception as exc:
            last = exc
            print("[wcx] %sconnect attempt %d/%d failed: %r"
                  % (label, i + 1, attempts, exc), flush=True)
            if i < attempts - 1:
                d = DELAYS[min(i, len(DELAYS) - 1)]
                print("[wcx] sleeping %ds before retry" % d, flush=True)
                time.sleep(d)
    raise RuntimeError("connect failed after %d attempts: %r" % (attempts, last))


class Session:
    def __init__(self, label=""):
        self.label = label
        self.client = None

    def _ensure(self):
        if self.client is None:
            self.client = connect_retry(label=self.label)
        return self.client

    def _drop(self):
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
        self.client = None

    def run(self, cmd, timeout=120, attempts=3):
        last = None
        for i in range(attempts):
            try:
                return _remote.run(self._ensure(), cmd, timeout=timeout, echo=False)
            except Exception as exc:
                last = exc
                print("[wcx] %srun attempt %d/%d failed: %r"
                      % (self.label, i + 1, attempts, exc), flush=True)
                self._drop()
                if i < attempts - 1:
                    time.sleep(DELAYS[min(i, len(DELAYS) - 1)])
        raise RuntimeError("run failed after %d attempts: %r" % (attempts, last))

    def out(self, cmd, timeout=120, attempts=3, default=None):
        """Like run() but returns stdout, or `default` instead of raising."""
        try:
            return self.run(cmd, timeout=timeout, attempts=attempts)[1]
        except Exception as exc:
            if default is None:
                raise
            return "%s %r" % (default, exc)

    def close(self):
        self._drop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
