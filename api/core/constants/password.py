"""
Password-related constants.
"""
import os

# Minimum password length for all user creation and password reset operations
# Can be overridden with MIN_PASSWORD_LENGTH environment variable
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))

# Password complexity requirements
PASSWORD_COMPLEXITY = {
    "require_uppercase": True,
    "require_lowercase": True,
    "require_numbers": True,
    "require_special_chars": True,
    "special_chars": "!@#$%^&*()_+-=[]{}|;:,.<>?"
}
