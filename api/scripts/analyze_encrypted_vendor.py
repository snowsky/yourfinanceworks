#!/usr/bin/env python3
"""
Analyze the specific encrypted vendor data that's causing issues.
"""

import base64
import os
import sys

# Add the API directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.encryption_service import get_encryption_service
from core.models.database import set_tenant_context

def main():
    encrypted_data = "2IYTe3Opx6c7fMxkTz+CIDb2D3CnBRGiFlOrDt2gXyM9iYw="
    
    print(f"Analyzing encrypted data: {encrypted_data}")
    print(f"Length: {len(encrypted_data)} characters")
    
    try:
        # Decode base64
        decoded = base64.b64decode(encrypted_data)
        print(f"Base64 decoded successfully, length: {len(decoded)} bytes")
        
        if len(decoded) >= 12:
            nonce = decoded[:12]
            ciphertext = decoded[12:]
            print(f"Nonce length: {len(nonce)} bytes")
            print(f"Ciphertext length: {len(ciphertext)} bytes")
            print(f"Nonce (hex): {nonce.hex()}")
            print(f"Ciphertext (hex): {ciphertext.hex()}")
        else:
            print(f"Decoded data too short: {len(decoded)} bytes")
            return
            
    except Exception as e:
        print(f"Failed to decode base64: {e}")
        return
    
    # Try to decrypt using the encryption service
    try:
        set_tenant_context(1)
        encryption_service = get_encryption_service()
        
        print("\nAttempting decryption...")
        decrypted = encryption_service.decrypt_data(encrypted_data, 1)
        print(f"Decryption successful: {decrypted}")
        
    except Exception as e:
        print(f"Decryption failed: {e}")
        print(f"Error type: {type(e).__name__}")


if __name__ == "__main__":
    main()