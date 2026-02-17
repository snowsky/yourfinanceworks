#!/usr/bin/env python3
"""
Script to generate RSA key pair for license signing.

This script generates:
- private_key_v{version}.pem: Used by license server to sign licenses (keep secure!)
- public_key_v{version}.pem: Embedded in application to verify licenses
- Symlinks: private_key.pem -> private_key_v{version}.pem (for convenience)

The keys are stored in api/core/keys/ directory.
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os
import argparse

def generate_rsa_keypair(key_size=2048):
    """Generate RSA key pair for license signing"""
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    
    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem, public_pem


def find_latest_key_version(keys_dir):
    """Find the latest key version number in the keys directory."""
    import re
    max_version = 0
    for filename in os.listdir(keys_dir):
        match = re.match(r'private_key_v(\d+)\.pem', filename)
        if match:
            version = int(match.group(1))
            max_version = max(max_version, version)
    return max_version


def create_symlink(target, link_path):
    """Create a symlink, removing existing one if necessary."""
    try:
        if os.path.islink(link_path):
            os.unlink(link_path)
        elif os.path.exists(link_path):
            os.remove(link_path)
        os.symlink(target, link_path)
    except (OSError, NotImplementedError) as e:
        # Fallback: copy file if symlinks not supported (e.g., Windows without dev mode)
        import shutil
        print(f"Warning: Symlink not supported, copying file instead: {e}")
        shutil.copy2(os.path.join(os.path.dirname(link_path), target), link_path)


def main():
    """Generate and save RSA key pair"""
    
    parser = argparse.ArgumentParser(description='Generate RSA key pair for license signing')
    parser.add_argument('--version', '-v', type=str, default=None,
                        help='Key version (e.g., "v2"). If not specified, auto-increments.')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Overwrite existing keys without prompting')
    parser.add_argument('--non-interactive', action='store_true',
                        help='Run in non-interactive mode (auto-confirm)')
    args = parser.parse_args()
    
    # Create keys directory if it doesn't exist
    # Keys go in api/core/keys/ for license verification
    keys_dir = os.path.join(os.path.dirname(__file__), '..', 'core', 'keys')
    os.makedirs(keys_dir, exist_ok=True)
    
    # Determine key version
    if args.version:
        version = args.version if args.version.startswith('v') else f'v{args.version}'
    else:
        latest = find_latest_key_version(keys_dir)
        version = f'v{latest + 1}'
    
    # Define file paths
    versioned_private_key_path = os.path.join(keys_dir, f'private_key_{version}.pem')
    versioned_public_key_path = os.path.join(keys_dir, f'public_key_{version}.pem')
    symlink_private_key_path = os.path.join(keys_dir, 'private_key.pem')
    symlink_public_key_path = os.path.join(keys_dir, 'public_key.pem')
    
    # Check if keys already exist
    if os.path.exists(versioned_private_key_path) or os.path.exists(versioned_public_key_path):
        if not args.force:
            if args.non_interactive:
                print(f"Keys for version {version} already exist. Skipping generation.")
                return
            response = input(f"Keys for version {version} already exist. Overwrite? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted. Existing keys preserved.")
                return
    
    print(f"Generating RSA key pair (2048-bit) for version {version}...")
    private_pem, public_pem = generate_rsa_keypair()
    
    # Save versioned private key
    with open(versioned_private_key_path, 'wb') as f:
        f.write(private_pem)
    os.chmod(versioned_private_key_path, 0o600)  # Secure permissions
    
    # Save versioned public key
    with open(versioned_public_key_path, 'wb') as f:
        f.write(public_pem)
    os.chmod(versioned_public_key_path, 0o644)  # Readable by all
    
    # Create symlinks pointing to the new versioned keys
    create_symlink(os.path.basename(versioned_private_key_path), symlink_private_key_path)
    create_symlink(os.path.basename(versioned_public_key_path), symlink_public_key_path)
    
    print(f"\n✓ Private key saved to: {versioned_private_key_path}")
    print(f"✓ Public key saved to: {versioned_public_key_path}")
    print(f"✓ Symlink created: private_key.pem -> {os.path.basename(versioned_private_key_path)}")
    print(f"✓ Symlink created: public_key.pem -> {os.path.basename(versioned_public_key_path)}")
    print(f"✓ Private key permissions set to 600 (owner read/write only)")
    
    print("\n" + "=" * 60)
    print("⚠️  IMPORTANT SECURITY NOTES:")
    print("=" * 60)
    print(f"- Keys are stored in: {keys_dir}")
    print("- The private key is used to SIGN licenses (keep SECURE!)")
    print("- Keep private_key_*.pem SECURE and NEVER commit to version control")
    print("- The public key is used to VERIFY licenses (safe to distribute)")
    print("- Both keys are gitignored by default (.gitignore excludes *.pem)")
    print("=" * 60)


if __name__ == '__main__':
    main()
