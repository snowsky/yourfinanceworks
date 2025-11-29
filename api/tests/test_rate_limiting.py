"""
Test Rate Limiting Functionality

Simple test to verify rate limiting and quota enforcement.
"""

import time
from core.services.rate_limiter_service import RateLimiterService


def test_rate_limiting():
    """Test basic rate limiting functionality."""
    print("Testing rate limiting...")
    
    rate_limiter = RateLimiterService()
    api_client_id = "test_client_123"
    
    # Test 1: Check that requests within limits are allowed
    print("\n1. Testing requests within limits...")
    for i in range(5):
        allowed, error, retry_after = rate_limiter.check_rate_limit(
            api_client_id=api_client_id,
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
            rate_limit_per_day=1000
        )
        assert allowed, f"Request {i+1} should be allowed"
        print(f"   Request {i+1}: ✓ Allowed")
    
    # Test 2: Check that exceeding minute limit is blocked
    print("\n2. Testing minute rate limit...")
    for i in range(5):
        allowed, error, retry_after = rate_limiter.check_rate_limit(
            api_client_id=api_client_id,
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
            rate_limit_per_day=1000
        )
        if i < 5:  # We already made 5 requests, so next 5 should be allowed
            assert allowed, f"Request {i+6} should be allowed"
            print(f"   Request {i+6}: ✓ Allowed")
    
    # Now we've made 10 requests, next should be blocked
    allowed, error, retry_after = rate_limiter.check_rate_limit(
        api_client_id=api_client_id,
        rate_limit_per_minute=10,
        rate_limit_per_hour=100,
        rate_limit_per_day=1000
    )
    assert not allowed, "Request 11 should be blocked (minute limit)"
    assert "per minute" in error.lower()
    assert retry_after is not None and retry_after > 0
    print(f"   Request 11: ✓ Blocked (minute limit exceeded)")
    print(f"   Retry after: {retry_after} seconds")
    
    # Test 3: Check custom quotas
    print("\n3. Testing custom quotas...")
    rate_limiter.reset_limits(api_client_id)
    
    custom_quotas = {
        'rate_limit_per_minute': 3,
        'rate_limit_per_hour': 50,
        'rate_limit_per_day': 500
    }
    
    for i in range(3):
        allowed, error, retry_after = rate_limiter.check_rate_limit(
            api_client_id=api_client_id,
            rate_limit_per_minute=10,  # Default
            rate_limit_per_hour=100,   # Default
            rate_limit_per_day=1000,   # Default
            custom_quotas=custom_quotas  # Custom overrides
        )
        assert allowed, f"Request {i+1} should be allowed with custom quota"
        print(f"   Request {i+1}: ✓ Allowed (custom quota: 3/min)")
    
    # 4th request should be blocked due to custom quota
    allowed, error, retry_after = rate_limiter.check_rate_limit(
        api_client_id=api_client_id,
        rate_limit_per_minute=10,
        rate_limit_per_hour=100,
        rate_limit_per_day=1000,
        custom_quotas=custom_quotas
    )
    assert not allowed, "Request 4 should be blocked (custom minute limit)"
    print(f"   Request 4: ✓ Blocked (custom quota exceeded: 3/min)")
    
    # Test 4: Check usage tracking
    print("\n4. Testing usage tracking...")
    rate_limiter.reset_limits(api_client_id)
    
    for i in range(5):
        rate_limiter.check_rate_limit(
            api_client_id=api_client_id,
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
            rate_limit_per_day=1000
        )
    
    usage = rate_limiter.get_current_usage(api_client_id)
    assert usage['minute'] == 5, f"Expected 5 requests in minute window, got {usage['minute']}"
    assert usage['hour'] == 5, f"Expected 5 requests in hour window, got {usage['hour']}"
    assert usage['day'] == 5, f"Expected 5 requests in day window, got {usage['day']}"
    print(f"   Usage tracking: ✓ Correct (minute={usage['minute']}, hour={usage['hour']}, day={usage['day']})")
    
    print("\n✅ All rate limiting tests passed!")


def test_concurrent_jobs():
    """Test concurrent job limits (requires database)."""
    print("\nTesting concurrent job limits...")
    print("   ⚠️  Skipping (requires database connection)")
    print("   This would be tested in integration tests with actual database")


if __name__ == "__main__":
    test_rate_limiting()
    test_concurrent_jobs()
    print("\n" + "="*60)
    print("Rate limiting implementation complete!")
    print("="*60)
