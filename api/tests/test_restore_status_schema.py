"""Unit tests for RestoreStatementRequest.new_status constraint.

Regression coverage for a state-machine bypass: new_status was an open `Optional[str]`,
so a client could restore a statement into any status (e.g. "processing", implying an
in-flight OCR job that doesn't exist, or arbitrary garbage). It is now a Literal of safe
idle states.

Schema imports cleanly (pydantic only) — runs locally without the app env.
"""

import pytest
from pydantic import ValidationError

from core.schemas.bank_statement import RestoreStatementRequest


@pytest.mark.unit
class TestRestoreStatementRequest:
    def test_defaults_to_processed(self):
        assert RestoreStatementRequest().new_status == "processed"

    @pytest.mark.parametrize("status", ["pending", "uploaded", "processed", "failed"])
    def test_accepts_safe_states(self, status):
        assert RestoreStatementRequest(new_status=status).new_status == status

    @pytest.mark.parametrize("status", ["processing", "merged", "deleted", "", "ADMIN", "garbage"])
    def test_rejects_unsafe_or_unknown_states(self, status):
        with pytest.raises(ValidationError):
            RestoreStatementRequest(new_status=status)
