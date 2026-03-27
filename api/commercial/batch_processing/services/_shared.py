"""
Shared constants and imports for batch processing services.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

MAX_FILES_PER_BATCH = 50
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
ALLOWED_FILE_TYPES = {'.pdf', '.png', '.jpg', '.jpeg', '.csv'}

DOCUMENT_TYPE_TOPICS = {
    'invoice': 'invoices_ocr',
    'expense': 'expense_ocr',
    'statement': 'bank_statements_ocr'
}
