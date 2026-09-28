import threading
import time
from collections import defaultdict, deque


class UserRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = defaultdict(deque)

    def allow(self, user_id, per_minute, per_hour):
        now = time.time()
        minute_cutoff = now - 60
        hour_cutoff = now - 3600

        with self._lock:
            q = self._events[user_id]
            while q and q[0] < hour_cutoff:
                q.popleft()

            minute_count = sum(1 for ts in q if ts >= minute_cutoff)
            if minute_count >= per_minute or len(q) >= per_hour:
                return False

            q.append(now)
            return True

    def allow_window(self, key, limit, window_seconds):
        """Generic sliding window rate limiter for keys like IP or endpoint:user."""
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            q = self._events[key]
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= limit:
                return False

            q.append(now)
            return True


user_rate_limiter = UserRateLimiter()


def get_client_ip(req):
    """Safely extracts client IP address, respecting trusted proxy headers via ProxyFix."""
    return req.remote_addr or "127.0.0.1"
