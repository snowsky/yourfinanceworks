"""
File path validation utilities for security.

Provides functions to validate and sanitize file paths to prevent path traversal attacks.
"""

import os
from typing import Optional

from fastapi import HTTPException


def validate_file_path(file_path: str, must_exist: bool = True, base_dir: Optional[str] = None) -> str:
    """Validate and sanitize file path to prevent path traversal attacks.

    Args:
        file_path: The file path to validate
        must_exist: If True, the file must exist. If False, only validate the path structure.
        base_dir: If provided, the resolved path must start with this directory.
                  Use this to enforce that files stay within a known safe directory.

    Returns:
        str: The validated absolute path

    Raises:
        ValueError: If the path is invalid or unsafe
    """
    safe_path = os.path.abspath(file_path)
    if base_dir is not None:
        safe_base = os.path.abspath(base_dir)
        # Ensure trailing separator so "/safe/dir" doesn't prefix-match "/safe/dir-other"
        if not safe_path.startswith(safe_base + os.sep) and safe_path != safe_base:
            raise ValueError(f"Invalid or unsafe file path: {file_path}")
    if must_exist and not os.path.exists(safe_path):
        raise ValueError(f"Invalid or unsafe file path: {file_path}")
    return safe_path


def validate_file_magic_bytes(content: bytes, content_type: str) -> None:
    """Validate that file contents match the declared content type using magic bytes.

    Args:
        content: Raw file bytes to inspect.
        content_type: The MIME type declared by the client (e.g. "application/pdf").

    Raises:
        HTTPException 400: If the magic bytes do not match the declared content type.
    """
    if content_type == "application/pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="File content does not match declared type: expected a PDF file",
            )
    elif content_type in ("text/csv", "application/vnd.ms-excel"):
        # Reject obvious binary content: check that the first 512 bytes are valid UTF-8 text
        sample = content[:512]
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="File content does not match declared type: expected a text/CSV file",
            )
