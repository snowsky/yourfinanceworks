"""
License Service for Customer-Side License Verification

This service handles:
- License verification with JWT signature validation
- Trial management (30-day trial + 7-day grace period)
- License activation and deactivation
- Feature availability checks
- Caching for performance optimization
"""

import jwt
import hashlib
import uuid
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from core.models.models_per_tenant import InstallationInfo, LicenseValidationLog


# Default key ID for licenses without explicit kid
DEFAULT_KEY_ID = os.getenv("LICENSE_DEFAULT_KEY_ID", "v2")

# Keys directory path
KEYS_DIR = Path(__file__).parent.parent / "keys"


def generate_key_pair() -> tuple[str, str]:
    """
    Generate a new RSA key pair for license signing.
    
    Returns:
        Tuple of (private_key_pem, public_key_pem) as strings
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        print("Generating new RSA key pair (2048-bit)...")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Get public key
        public_key = private_key.public_key()
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return private_pem, public_pem
        
    except ImportError:
        raise ImportError(
            "cryptography package is required to generate keys. "
            "Install it with: pip install cryptography"
        )


def save_generated_keys(private_key: str, public_key: str, version: str = None) -> None:
    """
    Save generated keys to the keys directory.
    
    Args:
        private_key: Private key PEM string
        public_key: Public key PEM string
        version: Optional version identifier (e.g., "v2")
    """
    # Create keys directory if it doesn't exist
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine filenames
    if version:
        private_path = KEYS_DIR / f"private_key_{version}.pem"
        public_path = KEYS_DIR / f"public_key_{version}.pem"
    else:
        private_path = KEYS_DIR / "private_key.pem"
        public_path = KEYS_DIR / "public_key.pem"
    
    # Save private key
    private_path.write_text(private_key)
    os.chmod(private_path, 0o600)  # Secure permissions
    print(f"✓ Saved private key to: {private_path}")
    
    # Save public key
    public_path.write_text(public_key)
    os.chmod(public_path, 0o644)  # Readable by all
    print(f"✓ Saved public key to: {public_path}")
    
    # Create README if it doesn't exist
    readme_path = KEYS_DIR / "README.md"
    if not readme_path.exists():
        readme_path.write_text("""# Auto-Generated License Keys

These keys were automatically generated on first startup.

## Security Notes

⚠️ **IMPORTANT**: The private key must be kept secure!

- **private_key.pem** - Used to sign licenses (KEEP SECURE!)
  - Should only be on the license server
  - Never commit to version control
  - Permissions: 600 (owner read/write only)

- **public_key.pem** - Used to verify licenses
  - Embedded in the application
  - Safe to distribute
  - Permissions: 644 (readable by all)

## Key Rotation

To rotate keys, see: docs/admin-guide/LICENSE_KEY_ROTATION_GUIDE.md
""")
    
    print("\n" + "="*60)
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("="*60)
    print(f"- Private key saved to: {private_path}")
    print(f"- Keep the private key SECURE and NEVER commit to version control")
    print(f"- Add '{private_path.name}' to .gitignore")
    print(f"- Public key saved to: {public_path}")
    print(f"- The public key is safe to distribute with the application")
    print("="*60 + "\n")


def create_symlinks_to_latest_version() -> None:
    """
    Create symlinks from non-versioned names to the latest versioned files.
    
    This allows using 'private_key.pem' which points to 'private_key_v2.pem'
    making it easier to use without specifying versions.
    """
    if not KEYS_DIR.exists():
        return
    
    # Find the latest version by looking at versioned files
    versioned_private_keys = list(KEYS_DIR.glob("private_key_v*.pem"))
    versioned_public_keys = list(KEYS_DIR.glob("public_key_v*.pem"))
    
    if not versioned_private_keys and not versioned_public_keys:
        return  # No versioned keys to link to
    
    # Extract versions and find the latest (e.g., v2, v3, v10)
    versions = set()
    for key_file in versioned_private_keys + versioned_public_keys:
        # Extract version from filename (e.g., private_key_v2.pem -> v2)
        version = key_file.stem.split('_')[-1]  # Get last part after underscore
        if version.startswith('v'):
            versions.add(version)
    
    if not versions:
        return
    
    # Sort versions (v2, v3, v10, etc.) - handle numeric sorting
    def version_key(v):
        try:
            return int(v[1:])  # Remove 'v' and convert to int
        except:
            return 0
    
    latest_version = sorted(versions, key=version_key)[-1]
    
    # Create symlinks if they don't exist or point to wrong version
    private_link = KEYS_DIR / "private_key.pem"
    public_link = KEYS_DIR / "public_key.pem"
    
    private_target = f"private_key_{latest_version}.pem"
    public_target = f"public_key_{latest_version}.pem"
    
    # Check if target files exist
    if not (KEYS_DIR / private_target).exists() or not (KEYS_DIR / public_target).exists():
        return
    
    # Create/update private key symlink
    if private_link.is_symlink():
        current_target = os.readlink(private_link)
        if current_target != private_target:
            private_link.unlink()
            private_link.symlink_to(private_target)
            print(f"Updated symlink: private_key.pem -> {private_target}")
    elif not private_link.exists():
        private_link.symlink_to(private_target)
        print(f"Created symlink: private_key.pem -> {private_target}")
    
    # Create/update public key symlink
    if public_link.is_symlink():
        current_target = os.readlink(public_link)
        if current_target != public_target:
            public_link.unlink()
            public_link.symlink_to(public_target)
            print(f"Updated symlink: public_key.pem -> {public_target}")
    elif not public_link.exists():
        public_link.symlink_to(public_target)
        print(f"Created symlink: public_key.pem -> {public_target}")


def load_public_keys() -> Dict[str, str]:
    """
    Load public keys from files in the keys directory.

    If no keys are found, automatically generates a new key pair.
    Automatically creates symlinks from non-versioned names to latest version.

    Looks for files matching pattern: public_key_*.pem or public_key.pem
    The key version is extracted from the filename.

    Also supports loading from environment variables:
    - LICENSE_PUBLIC_KEY_V2, LICENSE_PUBLIC_KEY_V3, etc.

    Returns:
        Dict mapping key version to public key content
    """
    public_keys = {}

    # Create symlinks to latest version if versioned keys exist
    try:
        create_symlinks_to_latest_version()
    except Exception as e:
        print(f"Warning: Failed to create symlinks: {e}")

    # Load from environment variables first (highest priority)
    for env_var, value in os.environ.items():
        if env_var.startswith("LICENSE_PUBLIC_KEY_"):
            # Extract version from env var name (e.g., LICENSE_PUBLIC_KEY_V2 -> v2)
            version = env_var.replace("LICENSE_PUBLIC_KEY_", "").lower()
            public_keys[version] = value
            print(f"Loaded public key {version} from environment variable")
    
    # Load from files in keys directory
    if KEYS_DIR.exists():
        # Look for versioned keys: public_key_v2.pem, public_key_v3.pem, etc.
        for key_file in KEYS_DIR.glob("public_key_v*.pem"):
            # Extract version from filename (e.g., public_key_v2.pem -> v2)
            version = key_file.stem.replace("public_key_", "")
            if version not in public_keys:  # Don't override env vars
                try:
                    # Resolve symlinks to get actual file
                    actual_file = key_file.resolve()
                    with open(actual_file, "r") as f:
                        public_keys[version] = f.read()
                    print(f"Loaded public key {version} from {key_file}")
                except Exception as e:
                    print(f"Warning: Failed to load {key_file}: {e}")

        # Also check for default public_key.pem (maps to DEFAULT_KEY_ID)
        default_key_file = KEYS_DIR / "public_key.pem"
        if default_key_file.exists() and DEFAULT_KEY_ID not in public_keys:
            try:
                # Resolve symlinks to get actual file
                actual_file = default_key_file.resolve()
                with open(actual_file, "r") as f:
                    public_keys[DEFAULT_KEY_ID] = f.read()
                print(f"Loaded default public key as {DEFAULT_KEY_ID} from {default_key_file}")
            except Exception as e:
                print(f"Warning: Failed to load {default_key_file}: {e}")

        # Explicitly check for master_public_key.pem (central server key)
        # This allows verifying licenses signed by the server's master key
        master_key_file = KEYS_DIR / "master_public_key.pem"
        if master_key_file.exists():
            try:
                with open(master_key_file, "r") as f:
                    master_key_content = f.read()
                    # 'server_v1' is the dedicated ID for the master key
                    public_keys["server_v1"] = master_key_content
                print(f"Loaded master public key as 'server_v1' from {master_key_file}")
            except Exception as e:
                print(f"Warning: Failed to load {master_key_file}: {e}")

    # Auto-generate keys if none found
    if not public_keys:
        print("\n" + "="*60)
        print("No license keys found - generating new key pair...")
        print("="*60 + "\n")

        try:
            private_key, public_key = generate_key_pair()
            save_generated_keys(private_key, public_key, version=DEFAULT_KEY_ID)

            # Use the generated public key
            public_keys[DEFAULT_KEY_ID] = public_key
            print(f"✓ Generated and loaded new key pair as version {DEFAULT_KEY_ID}")

        except Exception as e:
            print(f"✗ Failed to generate keys: {e}")
            print("Please generate keys manually using: python api/scripts/generate_license_keys.py")
            raise RuntimeError(
                f"No license keys found and auto-generation failed: {e}\n"
                "Please generate keys manually or provide them via environment variables."
            )

    return public_keys


# Load public keys on module import
PUBLIC_KEYS = load_public_keys()

# Trial configuration
TRIAL_DURATION_DAYS = 30
GRACE_PERIOD_DAYS = 7
VALIDATION_CACHE_TTL_HOURS = 1


class LicenseService:
    """Service for managing license verification and trial functionality"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== License Verification ====================

    def verify_license(self, license_key: str) -> Dict[str, Any]:
        """
        Verify a license key using JWT signature verification.
        Supports multiple public keys for key rotation.

        Args:
            license_key: JWT license key to verify

        Returns:
            Dict with verification result:
            {
                "valid": bool,
                "payload": dict or None,
                "error": str or None,
                "error_code": str or None
            }
        """
        # First, decode without verification to get the key ID
        try:
            unverified_payload = jwt.decode(license_key, options={"verify_signature": False})
            key_id = unverified_payload.get("kid", DEFAULT_KEY_ID)
        except Exception:
            # If we can't decode at all, try with default key
            key_id = DEFAULT_KEY_ID
        
        # Get the appropriate public key
        public_key = PUBLIC_KEYS.get(key_id)
        if not public_key:
            return {
                "valid": False,
                "payload": None,
                "error": f"Unknown key ID: {key_id}. This license may be from an unsupported version.",
                "error_code": "UNKNOWN_KEY_ID"
            }

        try:
            # Check if we should allow expired licenses for testing
            allow_expired = os.getenv("ALLOW_EXPIRED_LICENSES", "false").lower() == "true"
            
            # Decode and verify JWT signature with the correct key
            if allow_expired:
                # For testing: decode without expiration verification, then check manually
                payload = jwt.decode(
                    license_key,
                    public_key,
                    algorithms=["RS256"],
                    options={"verify_exp": False}  # Don't verify expiration automatically
                )
                
                # Manual expiration check with warning
                exp_timestamp = payload.get("exp")
                if exp_timestamp:
                    exp_date = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    if datetime.now(timezone.utc) > exp_date:
                        import warnings
                        warnings.warn("Expired license being activated (ALLOW_EXPIRED_LICENSES=true)", UserWarning)
            else:
                # Normal verification with automatic expiration checking
                payload = jwt.decode(
                    license_key,
                    public_key,
                    algorithms=["RS256"]
                )

            # Verify required fields
            required_fields = ["customer_email", "features"]
            missing_fields = [f for f in required_fields if f not in payload]
            if missing_fields:
                return {
                    "valid": False,
                    "payload": payload,
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "error_code": "MALFORMED"
                }

            return {
                "valid": True,
                "payload": payload,
                "error": None,
                "error_code": None
            }

        except jwt.ExpiredSignatureError:
            # Check if we should allow expired licenses for testing
            allow_expired = os.getenv("ALLOW_EXPIRED_LICENSES", "false").lower() == "true"
            
            if allow_expired:
                # For testing: decode without verification to get the payload
                try:
                    payload = jwt.decode(
                        license_key,
                        options={"verify_signature": False, "verify_exp": False}
                    )
                    import warnings
                    warnings.warn("Expired license being activated (ALLOW_EXPIRED_LICENSES=true)", UserWarning)
                    return {
                        "valid": True,
                        "payload": payload,
                        "error": None,
                        "error_code": None
                    }
                except Exception:
                    pass
            
            return {
                "valid": False,
                "payload": None,
                "error": "License signature has expired",
                "error_code": "EXPIRED"
            }
        except jwt.InvalidSignatureError:
            return {
                "valid": False,
                "payload": None,
                "error": "Invalid license signature",
                "error_code": "INVALID_SIGNATURE"
            }
        except jwt.DecodeError:
            return {
                "valid": False,
                "payload": None,
                "error": "Malformed license key",
                "error_code": "MALFORMED"
            }
        except Exception as e:
            return {
                "valid": False,
                "payload": None,
                "error": f"License verification failed: {str(e)}",
                "error_code": "VERIFICATION_ERROR"
            }

    def _get_license_key_hash(self, license_key: str) -> str:
        """Generate SHA-256 hash of license key for logging"""
        return hashlib.sha256(license_key.encode()).hexdigest()

    def _log_validation(
        self,
        installation: InstallationInfo,
        validation_type: str,
        validation_result: str,
        license_key: Optional[str] = None,
        features: Optional[List[str]] = None,
        expiration_date: Optional[datetime] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log license validation attempt"""
        try:
            log_entry = LicenseValidationLog(
                installation_id=installation.id,
                validation_type=validation_type,
                validation_result=validation_result,
                license_key_hash=self._get_license_key_hash(license_key) if license_key else None,
                features_validated=features,
                expiration_date=expiration_date,
                error_code=error_code,
                error_message=error_message,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            self.db.add(log_entry)
            self.db.commit()
        except Exception as e:
            # Log the error but don't fail the operation
            logger.error(f"Failed to log promotion to tenant audit log: {e}")
            self.db.rollback()

    # ==================== Usage Type Selection ====================

    def select_usage_type(
        self,
        usage_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Select usage type: personal (free) or business (30-day trial).

        Args:
            usage_type: Either "personal" or "business"
            user_id: ID of user making the selection
            ip_address: IP address of request
            user_agent: User agent string

        Returns:
            Dict with selection result
        """
        if usage_type not in ["personal", "business"]:
            return {
                "success": False,
                "message": "Invalid usage type. Must be 'personal' or 'business'",
                "error": "INVALID_USAGE_TYPE"
            }

        installation = self._get_or_create_installation()

        # Check if usage type already selected
        if installation.usage_type is not None:
            return {
                "success": False,
                "message": f"Usage type already selected as '{installation.usage_type}'",
                "error": "ALREADY_SELECTED"
            }

        now = datetime.now(timezone.utc)
        installation.usage_type = usage_type
        installation.usage_type_selected_at = now

        if usage_type == "personal":
            # Personal use: free forever, all features enabled
            installation.license_status = "personal"
            installation.trial_start_date = None
            installation.trial_end_date = None

            self.db.commit()
            self.db.refresh(installation)

            # Log personal use selection
            self._log_validation(
                installation=installation,
                validation_type="usage_type_selected",
                validation_result="success",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )

            return {
                "success": True,
                "message": "Personal use selected. All features are available for free.",
                "usage_type": "personal",
                "license_status": "personal"
            }

        else:  # business
            # Business use: 30-day trial
            trial_end = now + timedelta(days=TRIAL_DURATION_DAYS)
            installation.license_status = "trial"
            installation.trial_start_date = now
            installation.trial_end_date = trial_end

            self.db.commit()
            self.db.refresh(installation)

            # Log trial start
            self._log_validation(
                installation=installation,
                validation_type="trial_start",
                validation_result="success",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            return {
                "success": True,
                "message": f"Business trial started. {TRIAL_DURATION_DAYS} days remaining.",
                "usage_type": "business",
                "license_status": "trial",
                "trial_days_remaining": TRIAL_DURATION_DAYS,
                "trial_end_date": trial_end.isoformat()
            }
    
    def get_usage_type_status(self) -> Dict[str, Any]:
        """
        Get usage type selection status.

        Returns:
            Dict with usage type information
        """
        installation = self._get_or_create_installation()

        return {
            "usage_type": installation.usage_type,
            "usage_type_selected": installation.usage_type is not None,
            "usage_type_selected_at": installation.usage_type_selected_at.isoformat() if installation.usage_type_selected_at else None,
            "license_status": installation.license_status
        }

    # ==================== Trial Management ====================

    def _get_or_create_installation(self) -> InstallationInfo:
        """Get existing installation or create new one with invalid status"""
        installation = self.db.query(InstallationInfo).first()
        
        if not installation:
            # Auto-create installation record on first startup with invalid status
            # User must choose personal or business use
            installation = InstallationInfo(
                installation_id=str(uuid.uuid4()),
                license_status="invalid",
                usage_type=None,
                trial_start_date=None,
                trial_end_date=None
            )
            self.db.add(installation)
            self.db.commit()
            self.db.refresh(installation)
            
            # Log installation creation
            self._log_validation(
                installation=installation,
                validation_type="installation_created",
                validation_result="success"
            )
        
        return installation
    
    def is_trial_active(self) -> bool:
        """
        Check if 30-day trial is still active.
        
        Returns:
            True if trial is active, False otherwise
        """
        installation = self._get_or_create_installation()

        # If licensed or personal use, trial is not active
        if installation.license_status in ["active", "personal"]:
            return False

        # If no trial dates set, trial is not active
        if not installation.trial_end_date:
            return False

        now = datetime.now(timezone.utc)

        # Check if trial extension exists
        if installation.trial_extended_until:
            trial_extended = installation.trial_extended_until
            if trial_extended.tzinfo is None:
                trial_extended = trial_extended.replace(tzinfo=timezone.utc)
            return now <= trial_extended

        # Check standard trial period
        trial_end = installation.trial_end_date
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        return now <= trial_end

    def get_trial_status(self) -> Dict[str, Any]:
        """
        Get detailed trial status information.

        Returns:
            Dict with trial status:
            {
                "is_trial": bool,
                "trial_active": bool,
                "trial_start_date": datetime,
                "trial_end_date": datetime,
                "days_remaining": int,
                "in_grace_period": bool,
                "grace_period_end": datetime or None
            }
        """
        installation = self._get_or_create_installation()
        now = datetime.now(timezone.utc)

        # If no trial dates, return inactive trial status
        if not installation.trial_end_date:
            return {
                "is_trial": installation.license_status == "trial",
                "trial_active": False,
                "trial_start_date": installation.trial_start_date,
                "trial_end_date": None,
                "days_remaining": 0,
                "in_grace_period": False,
                "grace_period_end": None
            }

        # Determine effective trial end date
        trial_end = installation.trial_extended_until or installation.trial_end_date

        # Ensure trial_end is timezone-aware
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)

        # Calculate days remaining
        days_remaining = (trial_end - now).days if now <= trial_end else 0

        # Check if in grace period
        grace_period_end = trial_end + timedelta(days=GRACE_PERIOD_DAYS)
        in_grace_period = trial_end < now <= grace_period_end

        return {
            "is_trial": installation.license_status == "trial",
            "trial_active": now <= trial_end,
            "trial_start_date": installation.trial_start_date,
            "trial_end_date": trial_end,
            "days_remaining": max(0, days_remaining),
            "in_grace_period": in_grace_period,
            "grace_period_end": grace_period_end if in_grace_period else None
        }
    
    def is_in_grace_period(self) -> bool:
        """
        Check if installation is in grace period (7 days after trial expiration).

        Returns:
            True if in grace period, False otherwise
        """
        trial_status = self.get_trial_status()
        return trial_status["in_grace_period"]
    
    # ==================== License Activation ====================
    
    def activate_license(
        self,
        license_key: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Activate a license key and save to database.

        Args:
            license_key: JWT license key to activate
            user_id: ID of user activating the license
            ip_address: IP address of activation request
            user_agent: User agent string
            
        Returns:
            Dict with activation result:
            {
                "success": bool,
                "message": str,
                "features": list or None,
                "expires_at": datetime or None,
                "error": str or None
            }
        """
        # Verify license
        verification = self.verify_license(license_key)

        installation = self._get_or_create_installation()

        if not verification["valid"]:
            # Log failed activation
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code=verification["error_code"],
                error_message=verification["error"],
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )

            return {
                "success": False,
                "message": verification["error"],
                "features": None,
                "expires_at": None,
                "error": verification["error"]
            }

        # Extract license information
        payload = verification["payload"]
        features = payload.get("features", [])
        exp_timestamp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else None

        # Verify installation ID matches
        license_installation_id = payload.get("installation_id")
        if not license_installation_id:
            # Check if installation_id is in metadata (for backward compatibility)
            metadata = payload.get("metadata", {})
            license_installation_id = metadata.get("installation_id")

        if not license_installation_id:
            # Log failed activation - missing installation ID
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code="MISSING_INSTALLATION_ID",
                error_message="License is missing installation_id field",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )

            return {
                "success": False,
                "message": "License is missing installation identifier",
                "features": None,
                "expires_at": None,
                "error": "MISSING_INSTALLATION_ID"
            }

        if license_installation_id != installation.installation_id:
            # Log failed activation - installation ID mismatch
            self._log_validation(
                installation=installation,
                validation_type="activation",
                validation_result="failed",
                license_key=license_key,
                error_code="INSTALLATION_ID_MISMATCH",
                error_message=f"License installation_id '{license_installation_id}' does not match current installation '{installation.installation_id}'",
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )

            return {
                "success": False,
                "message": "This license is not valid for this installation",
                "features": None,
                "expires_at": None,
                "error": "INSTALLATION_ID_MISMATCH"
            }

        # Update installation record
        now = datetime.now(timezone.utc)
        installation.license_key = license_key
        installation.license_activated_at = now
        installation.license_expires_at = expires_at
        installation.license_status = "active"
        installation.licensed_features = features
        installation.customer_email = payload.get("customer_email")
        installation.customer_name = payload.get("customer_name")
        installation.organization_name = payload.get("organization_name")

        # If usage type not set, set it to business (since they're activating a paid license)
        if not installation.usage_type:
            installation.usage_type = "business"
            installation.usage_type_selected_at = now

        # Update validation cache
        installation.last_validation_at = now
        installation.last_validation_result = True
        installation.validation_cache_expires_at = now + timedelta(hours=VALIDATION_CACHE_TTL_HOURS)

        self.db.commit()
        self.db.refresh(installation)

        # Log successful activation
        self._log_validation(
            installation=installation,
            validation_type="activation",
            validation_result="success",
            license_key=license_key,
            features=features,
            expiration_date=expires_at,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        return {
            "success": True,
            "message": "License activated successfully",
            "features": features,
            "expires_at": expires_at,
            "error": None
        }
    
    def deactivate_license(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deactivate the current license and revert to trial.

        Args:
            user_id: ID of user deactivating the license
            ip_address: IP address of deactivation request
            user_agent: User agent string
            
        Returns:
            Dict with deactivation result:
            {
                "success": bool,
                "message": str
            }
        """
        installation = self._get_or_create_installation()

        # Store old license key for logging
        old_license_key = installation.license_key

        # Clear license information
        installation.license_key = None
        installation.license_activated_at = None
        installation.license_expires_at = None
        installation.license_status = "trial"
        installation.licensed_features = None
        installation.customer_email = None
        installation.customer_name = None
        installation.organization_name = None

        # Clear validation cache
        installation.last_validation_at = None
        installation.last_validation_result = None
        installation.validation_cache_expires_at = None

        self.db.commit()

        # Log deactivation
        self._log_validation(
            installation=installation,
            validation_type="deactivation",
            validation_result="success",
            license_key=old_license_key,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            "success": True,
            "message": "License deactivated successfully"
        }
    
    # ==================== Feature Checks ====================
    
    def get_enabled_features(self) -> List[str]:
        """
        Get list of licensed features.
        
        Returns:
            List of feature IDs that are enabled
        """
        installation = self._get_or_create_installation()

        # If personal use, only core features are enabled
        if installation.license_status == "personal":
            return ["core"]

        # If in trial or grace period, all features are enabled
        if self.is_trial_active() or self.is_in_grace_period():
            return ["all"]  # Special value indicating all features available

        # If licensed, return licensed features plus core
        if installation.license_status == "active" and installation.licensed_features:
            # Check if license is expired
            is_expired = False
            if installation.license_expires_at:
                expires_at = installation.license_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    is_expired = True
                    
                    # Check if we should allow expired licenses for testing
                    allow_expired = os.getenv("ALLOW_EXPIRED_LICENSES", "false").lower() == "true"
                    
                    if not allow_expired:
                        # License expired, update status
                        installation.license_status = "expired"
                        self.db.commit()
                        return ["core"]  # Fallback to core on expiration

            # If license is expired, only return core features (even for testing)
            if is_expired:
                return ["core"]

            # Check validation cache
            now = datetime.now(timezone.utc)
            cache_valid = False

            if installation.validation_cache_expires_at:
                cache_expires = installation.validation_cache_expires_at
                if cache_expires.tzinfo is None:
                    cache_expires = cache_expires.replace(tzinfo=timezone.utc)
                cache_valid = now < cache_expires and installation.last_validation_result

            # If cache is valid, return cached result
            if cache_valid:
                return (installation.licensed_features or []) + ["core"]

            # Cache expired or missing - re-verify license if we have a key
            if installation.license_key:
                verification = self.verify_license(installation.license_key)

                # Update cache
                installation.last_validation_at = now
                installation.last_validation_result = verification["valid"]
                installation.validation_cache_expires_at = now + timedelta(hours=VALIDATION_CACHE_TTL_HOURS)
                self.db.commit()

                if verification["valid"]:
                    return (installation.licensed_features or []) + ["core"]
                else:
                    # License verification failed
                    self._log_validation(
                        installation=installation,
                        validation_type="periodic_check",
                        validation_result="failed",
                        license_key=installation.license_key,
                        error_code=verification["error_code"],
                        error_message=verification["error"]
                    )
                    return ["core"]  # Fallback to core if verification fails

            # No license key but has licensed_features (shouldn't happen in production)
            # Trust the licensed_features since license hasn't expired
            return (installation.licensed_features or []) + ["core"]

        # No active license or trial
        return []
    
    def has_feature(self, feature_id: str, tier: str = "commercial") -> bool:
        """
        Check if a specific feature is enabled.

        Args:
            feature_id: Feature ID to check (e.g., "ai_invoice", "tax_integration")
            tier: License tier of the feature ("core" or "commercial")

        Returns:
            True if feature is enabled, False otherwise
        """
        enabled_features = self.get_enabled_features()

        # "all" means all features are enabled (trial/grace period)
        if "all" in enabled_features:
            return True

        # If checking for a core feature, it's enabled if "core" is in the list
        if tier == "core":
            return "core" in enabled_features or "all" in enabled_features
        
        # For commercial features, check specific ID
        return feature_id in enabled_features

    def has_feature_for_gating(self, feature_id: str, tier: str = "commercial") -> bool:
        """
        Check if a specific feature is enabled for API gating purposes.
        This method ignores ALLOW_EXPIRED_LICENSES and checks actual expiration status.

        Args:
            feature_id: Feature ID to check (e.g., "ai_invoice", "tax_integration")
            tier: License tier of the feature ("core" or "commercial")

        Returns:
            True if feature is enabled, False otherwise
        """
        installation = self._get_or_create_installation()

        # If personal use, only core features are enabled
        if installation.license_status == "personal":
            return tier == "core"

        # If in trial or grace period, all features are enabled
        if self.is_trial_active() or self.is_in_grace_period():
            return True

        # If licensed, check if actually expired (ignore ALLOW_EXPIRED_LICENSES)
        if installation.license_status == "active" and installation.licensed_features:
            # Always check actual expiration for gating
            if installation.license_expires_at:
                expires_at = installation.license_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    return False  # Expired licenses cannot access features for gating

            # License is active (not expired), check features
            licensed_features = installation.licensed_features or []
            if tier == "core":
                return True  # Core features always available with active license
            if "all" in licensed_features:
                return True
            return feature_id in licensed_features

        # No active license or trial
        return False

    def has_feature_read_only(self, feature_id: str, tier: str = "commercial") -> bool:
        """
        Check if a specific feature is enabled for read-only access.
        This allows users to view existing resources even with expired licenses,
        but blocks write operations.

        Args:
            feature_id: Feature ID to check (e.g., "cloud_storage", "ai_invoice")
            tier: License tier of the feature ("core" or "commercial")

        Returns:
            True if feature is available for read-only access, False otherwise
        """
        installation = self._get_or_create_installation()

        # If personal use, only core features are enabled
        if installation.license_status == "personal":
            return tier == "core"

        # If in trial or grace period, all features are enabled
        if self.is_trial_active() or self.is_in_grace_period():
            return True

        # If licensed (including expired), allow read access to previously licensed features
        if installation.license_status in ["active", "expired"] and installation.licensed_features:
            licensed_features = installation.licensed_features or []
            if tier == "core":
                return True  # Core features always available for read access
            return feature_id in licensed_features

        # No active license or trial
        return False

    # ==================== Status Information ====================
    
    def get_expired_features(self) -> List[str]:
        """
        Get list of features that were previously licensed but now expired.

        This allows the frontend to show content for expired features with a 
        renewal reminder, instead of completely hiding them.

        Returns:
            List of feature IDs that were licensed but now expired, empty list otherwise
        """
        installation = self._get_or_create_installation()

        # Only return expired features if we had licensed features
        if not installation.licensed_features:
            return []

        # Check if license is actually expired (ignore ALLOW_EXPIRED_LICENSES for this check)
        if installation.license_expires_at:
            expires_at = installation.license_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return installation.licensed_features

        # Also check if license status is explicitly set to expired
        if installation.license_status == "expired":
            return installation.licensed_features

        return []

    def is_license_expired(self) -> bool:
        """
        Check if the commercial license has expired.

        Returns:
            True if there was a license that is now expired, False otherwise
        """
        installation = self._get_or_create_installation()

        # Explicitly expired status
        if installation.license_status == "expired":
            return True

        # Check if license is marked active but actually expired
        if installation.license_status == "active" and installation.license_expires_at:
            expires_at = installation.license_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return True

        return False


    def get_license_status(self) -> Dict[str, Any]:
        """
        Get comprehensive license status information.

        Returns:
            Dict with complete license status
        """
        installation = self._get_or_create_installation()
        trial_status = self.get_trial_status()
        enabled_features = self.get_enabled_features()

        # Get license_type from JWT payload if available
        license_type = None
        if installation.license_key:
            try:
                # First try to decode without verification to get the license_type
                # This is safer than full verification for display purposes
                unverified_payload = jwt.decode(installation.license_key, options={"verify_signature": False})
                license_type = unverified_payload.get("license_type")

                # Also try full verification to ensure the license is valid
                verification = self.verify_license(installation.license_key)
                if not verification["valid"]:
                    # License is invalid, don't trust the unverified payload
                    license_type = None
            except Exception as e:
                # If anything fails, we can't extract license_type
                license_type = None

        # Get expired features for showing data with renewal banners
        expired_features = self.get_expired_features()
        is_expired = self.is_license_expired()

        return {
            "installation_id": installation.installation_id,
            "license_status": installation.license_status,
            "usage_type": installation.usage_type,
            "usage_type_selected": installation.usage_type is not None,
            "is_licensed": installation.license_status == "active",
            "is_personal": installation.license_status == "personal",
            "is_trial": installation.license_status == "trial",
            "is_license_expired": is_expired,  # True if license was active but now expired
            "license_type": license_type,  # Add the raw license_type from JWT
            "trial_info": trial_status,
            "license_info": {
                "activated_at": installation.license_activated_at,
                "expires_at": installation.license_expires_at,
                "customer_email": installation.customer_email,
                "customer_name": installation.customer_name,
                "organization_name": installation.organization_name
            } if installation.license_status in ["active", "expired"] else None,
            "enabled_features": enabled_features,
            "expired_features": expired_features,  # Features that were licensed but now expired
            "has_all_features": "all" in enabled_features
        }
