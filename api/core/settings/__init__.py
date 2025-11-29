"""
Settings package for the invoice application.

This package contains all configuration modules including:
- OCR configuration
- Cloud storage configuration
- Other application settings
"""

from .ocr_config import get_ocr_config, check_ocr_dependencies, is_ocr_available

__all__ = [
    'get_ocr_config',
    'check_ocr_dependencies', 
    'is_ocr_available'
]