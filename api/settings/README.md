# Settings Configuration

This directory contains all configuration modules for the invoice application.

## Modules

- **`ocr_config.py`** - OCR configuration for bank statement processing
- **`cloud_storage_config.py`** - Cloud storage configuration for multi-provider file storage

## Usage

```python
from settings import get_ocr_config, get_cloud_storage_config

# Get OCR configuration
ocr_config = get_ocr_config()

# Get cloud storage configuration  
storage_config = get_cloud_storage_config()
```

## Configuration Files

All configuration is loaded from environment variables. See the respective modules for available settings.

For cloud storage configuration details, see the original documentation in `settings/README.md`.