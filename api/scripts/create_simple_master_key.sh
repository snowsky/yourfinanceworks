#!/bin/bash
# Simple script to create a master.key file

set -e

KEY_DIR="/app/keys"
KEY_FILE="$KEY_DIR/master.key"

echo "🔑 Creating Master Key File"
echo "=========================="

# Create directory if it doesn't exist
mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR"

# Method 1: Generate random key
if [ "$1" = "random" ] || [ -z "$1" ]; then
    echo "🎲 Generating random 256-bit key..."
    # Generate 32 random bytes and encode as base64
    openssl rand -base64 32 > "$KEY_FILE"
    
# Method 2: Use provided base64 key
elif [ "$1" = "custom" ]; then
    if [ -z "$2" ]; then
        echo "❌ Error: Please provide base64 key as second argument"
        echo "Usage: $0 custom <base64-key>"
        exit 1
    fi
    echo "📝 Using provided base64 key..."
    echo "$2" > "$KEY_FILE"
    
# Method 3: Derive from passphrase
elif [ "$1" = "passphrase" ]; then
    if [ -z "$2" ]; then
        echo "❌ Error: Please provide passphrase as second argument"
        echo "Usage: $0 passphrase <your-passphrase>"
        exit 1
    fi
    echo "🔒 Deriving key from passphrase..."
    # Use PBKDF2 to derive key from passphrase
    echo -n "$2" | openssl dgst -sha256 -binary | openssl base64 > "$KEY_FILE"
    
else
    echo "❌ Invalid method: $1"
    echo "Usage: $0 [random|custom <base64-key>|passphrase <passphrase>]"
    exit 1
fi

# Set restrictive permissions
chmod 600 "$KEY_FILE"

# Verify the key
KEY_CONTENT=$(cat "$KEY_FILE")
echo "✅ Master key created successfully!"
echo "📁 Location: $KEY_FILE"
echo "🔐 Key (first 20 chars): ${KEY_CONTENT:0:20}..."
echo "📊 Key length: $(echo -n "$KEY_CONTENT" | wc -c) characters"

# Decode and check byte length
DECODED_LENGTH=$(echo "$KEY_CONTENT" | base64 -d | wc -c)
echo "🔢 Decoded length: $DECODED_LENGTH bytes"

if [ "$DECODED_LENGTH" -ne 32 ]; then
    echo "⚠️  Warning: Key should be 32 bytes (256 bits) for AES-256"
fi

echo ""
echo "🔧 To use this key, ensure your environment has:"
echo "   MASTER_KEY_PATH=$KEY_FILE"
echo ""
echo "🌍 Or set as environment variable:"
echo "   export MASTER_KEY='$KEY_CONTENT'"