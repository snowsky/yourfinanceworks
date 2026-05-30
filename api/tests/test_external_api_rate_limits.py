"""Tests that the external API enforces per-client rate limits.

Regression coverage for the bug where ExternalAPIAuthService.check_rate_limits
unconditionally returned (True, None, None), leaving the external statement-processing
API with no rate limiting (denial-of-wallet on LLM cost). It now delegates to the shared
RateLimiterService.

Two layers of coverage:
  * The enforcement logic (RateLimiterService) is tested directly — runs anywhere, since
    with REDIS_URL unset it uses an in-memory window.
  * The thin delegation in ExternalAPIAuthService.check_rate_limits is tested too, but its
    import drags in the full router package (Stripe etc.); that test is skipped when those
    transitive deps / env vars are unavailable locally and runs in Docker/CI.
"""

import asyncio
import os
from types import SimpleNamespace

import pytest

from core.services.rate_limiter_service import get_rate_limiter


def _client(client_id: str, per_minute=60, per_hour=1000, per_day=10000):
    return SimpleNamespace(
        client_id=client_id,
        rate_limit_per_minute=per_minute,
        rate_limit_per_hour=per_hour,
        rate_limit_per_day=per_day,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.unit
class TestRateLimiterEnforcement:
    """Directly exercise the limiter that check_rate_limits delegates to."""

    def test_allows_under_limit_then_blocks(self):
        rl = get_rate_limiter()
        allowed = [rl.check_rate_limit("rl-enforce", 3, 1000, 10000)[0] for _ in range(3)]
        assert allowed == [True, True, True]
        blocked, message, retry_after = rl.check_rate_limit("rl-enforce", 3, 1000, 10000)
        assert blocked is False
        assert message and "per minute" in message
        assert retry_after is None or retry_after >= 0

    def test_separate_clients_independent_budgets(self):
        rl = get_rate_limiter()
        assert rl.check_rate_limit("rl-a", 1, 1000, 10000)[0] is True
        assert rl.check_rate_limit("rl-a", 1, 1000, 10000)[0] is False
        assert rl.check_rate_limit("rl-b", 1, 1000, 10000)[0] is True


# --- Thin delegation through ExternalAPIAuthService (needs full app env) ---------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-rate-limit-tests")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-rate-limit-tests")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

try:
    from core.services.external_api_auth_service import ExternalAPIAuthService
    _SERVICE_IMPORT_ERROR = None
except Exception as exc:  # ImportError (e.g. stripe) / missing env in a bare local env
    ExternalAPIAuthService = None
    _SERVICE_IMPORT_ERROR = exc


@pytest.mark.unit
@pytest.mark.skipif(
    ExternalAPIAuthService is None,
    reason=f"ExternalAPIAuthService import unavailable locally: {_SERVICE_IMPORT_ERROR}",
)
class TestCheckRateLimitsDelegation:
    def test_delegates_and_blocks_over_limit(self):
        svc = ExternalAPIAuthService()
        client = _client("rl-delegate", per_minute=3)
        for _ in range(3):
            assert _run(svc.check_rate_limits(None, client))[0] is True
        allowed, message, _ = _run(svc.check_rate_limits(None, client))
        assert allowed is False
        assert message and "per minute" in message
