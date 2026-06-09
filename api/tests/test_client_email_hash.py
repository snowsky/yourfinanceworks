"""Tests for the client-email searchable hash (client portal lookup)."""

from core.utils.client_email_hash import compute_email_hash, normalize_email


def test_deterministic():
    a = compute_email_hash("client@example.com", 1)
    b = compute_email_hash("client@example.com", 1)
    assert a == b and a is not None


def test_normalization_case_and_whitespace():
    assert compute_email_hash("Client@Example.com", 1) == compute_email_hash("  client@example.com  ", 1)


def test_tenant_salting():
    # Same email, different tenant -> different hash (no cross-tenant correlation).
    assert compute_email_hash("client@example.com", 1) != compute_email_hash("client@example.com", 2)


def test_hex_length():
    h = compute_email_hash("client@example.com", 1)
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_none_email_returns_none():
    assert compute_email_hash(None, 1) is None
    assert compute_email_hash("", 1) is None
    assert compute_email_hash("   ", 1) is None


def test_none_tenant_returns_none():
    assert compute_email_hash("client@example.com", None) is None


def test_normalize_email():
    assert normalize_email("  Foo@Bar.COM ") == "foo@bar.com"
