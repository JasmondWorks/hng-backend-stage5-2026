# RFC DIVERGENCE: In-process sliding-window dict used instead of a distributed store.
# REASON: MVP scope — Redis dependency adds infrastructure complexity not yet warranted.
#         Replace _store with a Redis-backed implementation before horizontal scaling.
# DATE: 2026-05-13

# MVP only — replace with Redis under horizontal scaling.

import time
from collections import deque

_WINDOW_SECONDS = 60
_MAX_REQUESTS = 5

_store: dict[str, deque[float]] = {}


def check_rate_limit(user_id: str) -> int | None:
    """Check whether user_id has exceeded the rate limit.

    Returns the retry_after integer (seconds) if the limit is exceeded,
    or None if the request is allowed. Allowed requests are recorded.
    """
    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS

    if user_id not in _store:
        _store[user_id] = deque()

    timestamps = _store[user_id]

    # Evict timestamps that have fallen outside the sliding window.
    while timestamps and timestamps[0] < window_start:
        timestamps.popleft()

    if len(timestamps) >= _MAX_REQUESTS:
        oldest = timestamps[0]
        retry_after = int(oldest + _WINDOW_SECONDS - now) + 1
        return retry_after

    timestamps.append(now)
    return None
