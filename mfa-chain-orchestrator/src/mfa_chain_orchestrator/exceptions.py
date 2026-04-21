"""Custom exceptions for MFA chain orchestration."""


class MFAChainBreached(Exception):
    """Raised when an MFA step is attempted out of policy/session order."""

