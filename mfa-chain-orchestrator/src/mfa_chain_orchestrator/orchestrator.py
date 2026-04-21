"""MFA orchestration engine."""

from __future__ import annotations

import random

import pyotp

from .exceptions import MFAChainBreached
from .models import FactorDefinition, Policy, Result


class MFAOrchestrator:
    """Orchestrates per-session MFA factor chains from a policy."""

    RESET_LABEL: str = "RESET"

    def __init__(self, policy: Policy) -> None:
        self._policy = policy
        self._session_factors: list[FactorDefinition] = []
        self._cursor: int = 0
        self._initialized: bool = False

    @property
    def policy(self) -> Policy:
        """Return active policy."""
        return self._policy

    @property
    def current_factor(self) -> FactorDefinition:
        """Return currently expected factor.

        Raises:
            MFAChainBreached: If no active attempt exists or chain is complete.
        """
        if not self._initialized:
            raise MFAChainBreached("attempt is not initialized")
        if self._cursor >= len(self._session_factors):
            raise MFAChainBreached("attempt already completed")
        return self._session_factors[self._cursor]

    def initialize_attempt(self) -> list[FactorDefinition]:
        """Initialize a fresh MFA attempt and return ordered factors for the session."""
        if self._policy.mode == "fixed":
            self._session_factors = self._policy.factors[: self._policy.required_steps]
        else:
            self._session_factors = random.sample(self._policy.factors, self._policy.required_steps)

        self._cursor = 0
        self._initialized = True
        return list(self._session_factors)

    def verify_step(
        self,
        secret: str,
        user_input: str,
        window: int,
        factor_id: str | None = None,
    ) -> Result:
        """Verify the current MFA step with TOTP and advance only on success.

        Any failed step resets the chain and requires restart from the first factor.

        Args:
            secret: Base32-encoded shared secret for TOTP.
            user_input: 6-digit code provided by user.
            window: Valid time-step drift window for pyotp verification.
            factor_id: Optional caller-provided factor id; used to enforce strict ordering.

        Raises:
            MFAChainBreached: If attempt is uninitialized, already complete, or attempted out-of-order.
        """
        expected_factor = self.current_factor
        if factor_id is not None and factor_id != expected_factor.id:
            raise MFAChainBreached(
                f"out-of-order step attempt: expected '{expected_factor.id}' got '{factor_id}'"
            )

        if not self._is_valid_code(user_input):
            return self._reset_result()

        totp = pyotp.TOTP(secret)
        is_valid = bool(totp.verify(user_input, valid_window=window))
        if not is_valid:
            return self._reset_result()

        self._cursor += 1
        is_complete = self._cursor >= len(self._session_factors)
        if is_complete:
            return Result(success=True, is_complete=True, next_factor_label="")

        return Result(
            success=True,
            is_complete=False,
            next_factor_label=self._session_factors[self._cursor].label,
        )

    def _reset_result(self) -> Result:
        """Reset state after any failed verification attempt."""
        self._cursor = 0
        return Result(success=False, is_complete=False, next_factor_label=self.RESET_LABEL)

    @staticmethod
    def _is_valid_code(user_input: str) -> bool:
        """Perform strict 6-digit format validation before TOTP verification."""
        return len(user_input) == 6 and user_input.isdigit()
