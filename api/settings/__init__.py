"""
Settings package for the invoice application.

This package contains all configuration modules including:
- OCR configuration
- Cloud storage configuration
- Other application settings
"""

from .ocr_config import get_ocr_config, check_ocr_dependencies, is_ocr_available
from .cloud_storage_config import get_cloud_storage_config

__all__ = [
    'get_ocr_config',
    'check_ocr_dependencies', 
    'is_ocr_available',
    'get_cloud_storage_config'
]