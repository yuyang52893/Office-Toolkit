import ipaddress
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


# ponytail: process-local windows; move to Redis when deploying multiple backend instances.
class RateLimiter:
    def __init__(
        self,
        *,
        window_seconds: int,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = window_seconds
        self.max_entries = max_entries
        self.clock = clock
        self._windows: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int) -> RateLimitResult:
        now = self.clock()
        window_index = int(now // self.window_seconds)
        retry_after = max(1, math.ceil(self.window_seconds - (now % self.window_seconds)))

        with self._lock:
            if len(self._windows) >= self.max_entries:
                self._prune(window_index)
            state = self._windows.get(key)
            count = state[1] + 1 if state and state[0] == window_index else 1
            self._windows[key] = (window_index, count)

        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            remaining=max(limit - count, 0),
            retry_after=retry_after,
        )

    def _prune(self, current_window: int) -> None:
        stale = [key for key, (window, _) in self._windows.items() if window != current_window]
        for key in stale:
            self._windows.pop(key, None)
        while len(self._windows) >= self.max_entries:
            self._windows.pop(next(iter(self._windows)))


def resolve_client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        candidate = request.headers.get("x-real-ip", "").strip()
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return request.client.host if request.client else ""
