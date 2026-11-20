import logging
import threading
import time

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window limiter. Uses Redis when REDIS_URL is set, else an in-process store."""

    def __init__(self):
        self._mem: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        self._redis = None
        url = get_settings().redis_url
        if url:
            import redis

            self._redis = redis.Redis.from_url(url, socket_timeout=1)

    def hit(self, key: str, limit: int, window: int = 60) -> bool:
        if self._redis is not None:
            try:
                k = f"rl:{key}:{int(time.time() // window)}"
                n = self._redis.incr(k)
                if n == 1:
                    self._redis.expire(k, window)
                return n <= limit
            except Exception:  # Redis down: fall back to memory rather than fail open
                log.warning("Redis rate limiter unavailable; using in-memory fallback")
        with self._lock:
            count, start = self._mem.get(key, (0, time.time()))
            if time.time() - start >= window:
                count, start = 0, time.time()
            count += 1
            self._mem[key] = (count, start)
            return count <= limit

    def reset(self):
        with self._lock:
            self._mem.clear()


limiter = RateLimiter()


def auth_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not limiter.hit(f"auth:{ip}:{request.url.path}", get_settings().auth_rate_limit_per_minute):
        raise AppError(429, "rate_limited", "Too many requests, try again later")
