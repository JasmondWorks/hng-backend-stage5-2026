from unittest.mock import patch

from app.core import rate_limiter


class TestRateLimiter:
    def setup_method(self):
        rate_limiter._store.clear()

    def test_first_request_is_allowed(self):
        assert rate_limiter.check_rate_limit("user-a") is None

    def test_fifth_request_is_allowed(self):
        for _ in range(4):
            rate_limiter.check_rate_limit("user-b")
        result = rate_limiter.check_rate_limit("user-b")
        assert result is None

    def test_sixth_request_exceeds_limit_returns_retry_after(self):
        for _ in range(5):
            rate_limiter.check_rate_limit("user-c")
        result = rate_limiter.check_rate_limit("user-c")
        assert result is not None
        assert isinstance(result, int)
        assert result >= 1

    def test_retry_after_is_within_window(self):
        for _ in range(5):
            rate_limiter.check_rate_limit("user-d")
        result = rate_limiter.check_rate_limit("user-d")
        assert result is not None
        assert 1 <= result <= 60

    def test_different_users_have_independent_windows(self):
        for _ in range(5):
            rate_limiter.check_rate_limit("user-e")
        # A completely different user should not be affected.
        assert rate_limiter.check_rate_limit("user-f") is None

    def test_window_resets_after_60_seconds(self):
        base_time = 1_000.0

        with patch("app.core.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = base_time
            for _ in range(5):
                rate_limiter.check_rate_limit("user-g")

            # Advance 61 s — all previous timestamps fall outside the window.
            mock_time.monotonic.return_value = base_time + 61.0
            result = rate_limiter.check_rate_limit("user-g")

        assert result is None

    def test_partial_window_still_blocks(self):
        base_time = 1_000.0

        with patch("app.core.rate_limiter.time") as mock_time:
            mock_time.monotonic.return_value = base_time
            for _ in range(5):
                rate_limiter.check_rate_limit("user-h")

            # Advance only 30 s — still within the window.
            mock_time.monotonic.return_value = base_time + 30.0
            result = rate_limiter.check_rate_limit("user-h")

        assert result is not None

    def test_seventh_request_also_blocked(self):
        for _ in range(5):
            rate_limiter.check_rate_limit("user-i")
        rate_limiter.check_rate_limit("user-i")  # 6th (blocked but not recorded)
        result = rate_limiter.check_rate_limit("user-i")  # 7th
        assert result is not None
