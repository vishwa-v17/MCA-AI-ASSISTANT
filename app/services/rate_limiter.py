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


user_rate_limiter = UserRateLimiter()
