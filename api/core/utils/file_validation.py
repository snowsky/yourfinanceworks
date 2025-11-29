"""
File path validation utilities for security.

Provides functions to validate and sanitize file paths to prevent path traversal attacks.
"""

import os


def validate_file_path(file_path: str, must_exist: bool = True) -> str:
    """Validate and sanitize file path to prevent path traversal attacks.
    
    Args:
        file_path: The file path to validate
        must_exist: If True, the file must exist. If False, only validate the path structure.
        
    Returns:
        str: The validated absolute path
        
    Raises:
        ValueError: If the path is invalid or unsafe
    """
    safe_path = os.path.abspath(file_path)
    if ".." in safe_path:
        raise ValueError(f"Invalid or unsafe file path: {file_path}")
    if must_exist and not os.path.exists(safe_path):
        raise ValueError(f"Invalid or unsafe file path: {file_path}")
    return safe_path
