"""
Shared constants and key management utilities for license service.
"""

import os
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Default key ID for licenses without explicit kid
DEFAULT_KEY_ID = os.getenv("LICENSE_DEFAULT_KEY_ID", "v2")

# Keys directory path
KEYS_DIR = Path(__file__).parent.parent.parent / "keys"

# Trial configuration
TRIAL_DURATION_DAYS = 30
GRACE_PERIOD_DAYS = 7
VALIDATION_CACHE_TTL_HOURS = 1


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
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # Get public key
        public_key = private_key.public_key()

        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

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
        readme_path.write_text(
            """# Auto-Generated License Keys

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
"""
        )

    print("\n" + "=" * 60)
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("=" * 60)
    print(f"- Private key saved to: {private_path}")
    print(f"- Keep the private key SECURE and NEVER commit to version control")
    print(f"- Add '{private_path.name}' to .gitignore")
    print(f"- Public key saved to: {public_path}")
    print(f"- The public key is safe to distribute with the application")
    print("=" * 60 + "\n")


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
        version = key_file.stem.split("_")[-1]  # Get last part after underscore
        if version.startswith("v"):
            versions.add(version)

    if not versions:
        return

    # Sort versions (v2, v3, v10, etc.) - handle numeric sorting
    def version_key(v):
        try:
            return int(v[1:])  # Remove 'v' and convert to int
        except Exception:
            return 0

    latest_version = sorted(versions, key=version_key)[-1]

    # Create symlinks if they don't exist or point to wrong version
    private_link = KEYS_DIR / "private_key.pem"
    public_link = KEYS_DIR / "public_key.pem"

    private_target = f"private_key_{latest_version}.pem"
    public_target = f"public_key_{latest_version}.pem"

    # Check if target files exist
    if (
        not (KEYS_DIR / private_target).exists()
        or not (KEYS_DIR / public_target).exists()
    ):
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

    # Load master public key from environment variable (highest priority for server_v1)
    master_key_env = os.getenv("LICENSE_MASTER_PUBLIC_KEY")
    if master_key_env:
        public_keys["server_v1"] = master_key_env
        print("Loaded master public key from LICENSE_MASTER_PUBLIC_KEY environment variable")

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
                print(
                    f"Loaded default public key as {DEFAULT_KEY_ID} from {default_key_file}"
                )
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

    # Warn if private key files are on the filesystem — recommend using env vars instead
    if KEYS_DIR.exists():
        fs_private_keys = list(KEYS_DIR.glob("private_key*.pem"))
        if fs_private_keys:
            env_key_provided = bool(
                os.getenv("DEPLOYMENT_PRIVATE_KEY") or os.getenv("PRIVATE_KEY")
            )
            if not env_key_provided:
                print(
                    "\nWARNING: License private key(s) found on filesystem: "
                    + ", ".join(str(p) for p in fs_private_keys)
                    + "\n  Consider moving private keys to a secret manager and injecting via "
                    "DEPLOYMENT_PRIVATE_KEY env var to avoid storing credentials on disk.\n"
                )

    # Check if we have LOCAL signing keys (not just the master server key)
    # The master_public_key.pem (server_v1) is for verifying server-issued licenses,
    # but we also need local keys for signing our own licenses
    local_keys = {k: v for k, v in public_keys.items() if k not in ["server_v1"]}

    # Check environment variable to control RSA key pair auto-generation
    auto_generate_keys = os.getenv("LICENSE_KEY_AUTO_GENERATE", "true").lower() == "true"

    # Auto-generate RSA key pair if no local signing keys found and auto-generation is enabled
    if not local_keys and auto_generate_keys:
        print("\n" + "=" * 60)
        print("No local license keys found - generating new key pair...")
        print("(master_public_key.pem exists for server license verification)")
        print("=" * 60 + "\n")

        try:
            private_key, public_key = generate_key_pair()
            save_generated_keys(private_key, public_key, version=DEFAULT_KEY_ID)

            # Use the generated public key
            public_keys[DEFAULT_KEY_ID] = public_key
            print(f"✓ Generated and loaded new key pair as version {DEFAULT_KEY_ID}")

        except Exception as e:
            print(f"✗ Failed to generate keys: {e}")
            print(
                "Please generate keys manually using: python api/scripts/generate_license_keys.py"
            )
            raise RuntimeError(
                f"No local license keys found and auto-generation failed: {e}\n"
                "Please generate keys manually or provide them via environment variables."
            )
    elif not local_keys and not auto_generate_keys:
        print("\n" + "=" * 60)
        print("WARNING: No local RSA key pairs found and auto-generation is disabled")
        print("Set LICENSE_KEY_AUTO_GENERATE=true to enable auto-generation")
        print("Or generate keys manually: python api/scripts/generate_license_keys.py")
        print("=" * 60 + "\n")

    return public_keys


# Load public keys on module import
PUBLIC_KEYS = load_public_keys()
