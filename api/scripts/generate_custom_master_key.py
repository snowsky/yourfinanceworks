#!/usr/bin/env python3
"""
Generate a custom master key for database encryption.

This script allows you to create a custom master.key file with either:
1. A randomly generated secure key
2. A key derived from a passphrase
3. A key from existing base64 data
"""

import os
import sys
import secrets
import base64
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_random_key() -> bytes:
    """Generate a cryptographically secure random 256-bit key."""
    return secrets.token_bytes(32)

def derive_key_from_passphrase(passphrase: str, salt: str = "tenant_encryption_salt_2024") -> bytes:
    """
    Derive a 256-bit key from a passphrase using PBKDF2.
    
    Args:
        passphrase: User-provided passphrase
        salt: Salt for key derivation (should match your config)
    
    Returns:
        32-byte derived key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode('utf-8'),
        iterations=100000,  # Match your production settings
    )
    return kdf.derive(passphrase.encode('utf-8'))

def key_from_base64(base64_key: str) -> bytes:
    """
    Convert base64 string to key bytes.
    
    Args:
        base64_key: Base64 encoded key string
    
    Returns:
        Decoded key bytes
    """
    try:
        key_bytes = base64.b64decode(base64_key)
        if len(key_bytes) != 32:
            raise ValueError(f"Key must be 32 bytes (256 bits), got {len(key_bytes)} bytes")
        return key_bytes
    except Exception as e:
        raise ValueError(f"Invalid base64 key: {e}")

def save_master_key(key_bytes: bytes, key_path: str = "/app/keys/master.key"):
    """
    Save the master key to file with proper permissions.
    
    Args:
        key_bytes: 32-byte key
        key_path: Path to save the key file
    """
    # Ensure directory exists
    key_dir = Path(key_path).parent
    key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    
    # Encode key as base64 and save
    encoded_key = base64.b64encode(key_bytes)
    
    with open(key_path, 'wb') as f:
        f.write(encoded_key)
    
    # Set restrictive permissions
    os.chmod(key_path, 0o600)
    
    print(f"✅ Master key saved to: {key_path}")
    print(f"📊 Key length: {len(key_bytes)} bytes (256 bits)")
    print(f"🔐 Base64 encoded: {encoded_key.decode('utf-8')[:20]}...")

def main():
    """Main function with interactive key generation."""
    print("🔑 Custom Master Key Generator")
    print("=" * 40)
    
    print("\nChoose key generation method:")
    print("1. Generate random secure key (recommended)")
    print("2. Derive key from passphrase")
    print("3. Use existing base64 key")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        print("\n🎲 Generating random secure key...")
        key_bytes = generate_random_key()
        
    elif choice == "2":
        passphrase = input("\n🔒 Enter passphrase: ").strip()
        if len(passphrase) < 12:
            print("⚠️  Warning: Passphrase should be at least 12 characters for security")
        
        # Optional custom salt
        use_custom_salt = input("Use custom salt? (y/N): ").strip().lower() == 'y'
        if use_custom_salt:
            salt = input("Enter salt: ").strip()
        else:
            salt = "tenant_encryption_salt_2024"  # Default from config
        
        print(f"\n🔄 Deriving key from passphrase (salt: {salt[:10]}...)...")
        key_bytes = derive_key_from_passphrase(passphrase, salt)
        
    elif choice == "3":
        base64_key = input("\n📝 Enter base64 encoded key: ").strip()
        print("\n🔄 Decoding base64 key...")
        try:
            key_bytes = key_from_base64(base64_key)
        except ValueError as e:
            print(f"❌ Error: {e}")
            return 1
            
    else:
        print("❌ Invalid choice")
        return 1
    
    # Get output path
    default_path = "/app/keys/master.key"
    key_path = input(f"\n📁 Key file path (default: {default_path}): ").strip()
    if not key_path:
        key_path = default_path
    
    # Confirm before saving
    print(f"\n📋 Summary:")
    print(f"   Method: {['Random', 'Passphrase', 'Base64'][int(choice)-1]}")
    print(f"   Output: {key_path}")
    
    if input("\n💾 Save master key? (y/N): ").strip().lower() != 'y':
        print("❌ Cancelled")
        return 1
    
    try:
        save_master_key(key_bytes, key_path)
        
        # Show additional info
        encoded = base64.b64encode(key_bytes).decode('utf-8')
        print(f"\n📋 Key Information:")
        print(f"   Full base64: {encoded}")
        print(f"   SHA256 hash: {hashlib.sha256(key_bytes).hexdigest()[:16]}...")
        
        print(f"\n🔧 Environment Variable Option:")
        print(f"   export MASTER_KEY='{encoded}'")
        
        print(f"\n⚠️  Security Notes:")
        print(f"   - Keep this key secure and backed up")
        print(f"   - File permissions set to 600 (owner read/write only)")
        print(f"   - Consider using environment variables in production")
        
    except Exception as e:
        print(f"❌ Error saving key: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())