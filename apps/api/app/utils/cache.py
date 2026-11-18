import asyncio
import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable
from typing import Any


class TTLCache:
    """In-memory LRU + TTL cache; same URL ke parallel requests ek hi LLM call share karte hain."""

    # ponytail: per-process memory; multiple replicas chahiye to Redis lagao
    def __init__(self, ttl_seconds: int, max_entries: int):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[str, asyncio.Future] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.monotonic():
            self._data.pop(key, None)
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        self._data[key] = (time.monotonic() + self.ttl, value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)

    async def get_or_create(self, key: str, factory: Callable[[], Awaitable[Any]]) -> tuple[Any, bool]:
        if (hit := self.get(key)) is not None:
            return hit, True
        if key in self._inflight:
            return await asyncio.shield(self._inflight[key]), True
        future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            value = await factory()
            self.set(key, value)
            future.set_result(value)
            return value, False
        except asyncio.CancelledError:
            future.cancel()
            raise
        except Exception as exc:
            future.set_exception(exc)
            future.exception()  # waiter na ho to "never retrieved" warning se bachao
            raise
        finally:
            self._inflight.pop(key, None)


class RateLimiter:
    """Sliding window limiter per client IP."""

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def check(self, client: str) -> int | None:
        now = time.monotonic()
        hits = self._hits.setdefault(client, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return int(hits[0] + self.window - now) + 1
        hits.append(now)
        if len(self._hits) > 10_000:
            self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - self.window}
        return None
