"""
License service package.

Split from the original monolithic license_service.py (2,004 lines) into focused modules:
  - _shared.py    — Constants, key management utilities (generate_key_pair, load_public_keys, etc.)
  - validation.py — LicenseValidationMixin: JWT verification and validation logging
  - features.py   — LicenseFeaturesMixin: feature availability checks and gating
  - activation.py — LicenseActivationMixin: trial management, activation/deactivation,
                    installation ID management, and status reporting
"""

from typing import Optional

from sqlalchemy.orm import Session

from .validation import LicenseValidationMixin
from .features import LicenseFeaturesMixin
from .activation import LicenseActivationMixin

# Re-export module-level symbols consumed by other modules
from ._shared import (  # noqa: F401
    DEFAULT_KEY_ID,
    KEYS_DIR,
    PUBLIC_KEYS,
    TRIAL_DURATION_DAYS,
    GRACE_PERIOD_DAYS,
    VALIDATION_CACHE_TTL_HOURS,
    generate_key_pair,
    save_generated_keys,
    create_symlinks_to_latest_version,
    load_public_keys,
)


class LicenseService(
    LicenseValidationMixin,
    LicenseFeaturesMixin,
    LicenseActivationMixin,
):
    """Service for managing license verification and trial functionality.

    Implementation split across focused modules in the license_service/ package:
      - validation.py — JWT verification, validation logging
      - features.py   — Feature availability and gating
      - activation.py — Trial, activation, installation ID, status
    """

    def __init__(self, db: Session, master_db: Optional[Session] = None) -> None:
        self.db = db
        self.master_db = master_db


__all__ = [
    "LicenseService",
    "DEFAULT_KEY_ID",
    "KEYS_DIR",
    "PUBLIC_KEYS",
    "TRIAL_DURATION_DAYS",
    "GRACE_PERIOD_DAYS",
    "VALIDATION_CACHE_TTL_HOURS",
    "generate_key_pair",
    "save_generated_keys",
    "create_symlinks_to_latest_version",
    "load_public_keys",
]
