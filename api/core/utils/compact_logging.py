import json
import logging
import re
from typing import Any, Dict

class CompactJSONFormatter(logging.Formatter):
    """
    A specialized JSON formatter that masks sensitive information
    and provides a compact output format.
    """

    # regex for OpenAI-style and general API keys: sk-... followed by 20+ chars
    # or just a general hex/alphanumeric key
    API_KEY_PATTERN = re.compile(r'(sk-[a-zA-Z0-9]{20,})|([a-zA-Z0-9]{32,})')

    SENSITIVE_KEYS = {'api_key', 'api_secret', 'password', 'token', 'access_token', 'private_key'}

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": self._mask_sensitive(record.getMessage())
        }

        # Include extra attributes if present
        if hasattr(record, 'extra'):
            log_data.update(self._mask_dict(record.extra))

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

    def _mask_sensitive(self, text: str) -> str:
        """Mask API keys in plain text messages"""
        if not isinstance(text, str):
            return text

        def mask_match(match):
            key = match.group(0)
            if key.startswith('sk-'):
                return f"{key[:7]}...****"
            return f"{key[:4]}...****"

        return self.API_KEY_PATTERN.sub(mask_match, text)

    def _mask_dict(self, data: Any) -> Any:
        """Recursively mask sensitive keys in dictionaries"""
        if isinstance(data, dict):
            return {k: self._mask_value(k, v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._mask_dict(i) for i in data]
        return data

    def _mask_value(self, key: str, value: Any) -> Any:
        if key.lower() in self.SENSITIVE_KEYS and isinstance(value, str):
            if value.startswith('sk-'):
                return f"{value[:7]}...****"
            return f"{value[:4]}...****"
        return self._mask_dict(value)

def setup_secure_logging(log_level=logging.INFO):
    """Set up the secure JSON logger as the default handler"""
    handler = logging.StreamHandler()
    handler.setFormatter(CompactJSONFormatter())

    root_logger = logging.getLogger()

    # Remove existing handlers
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Specifically target AI loggers
    for logger_name in ['commercial.ai', 'litellm']:
        ai_logger = logging.getLogger(logger_name)
        ai_logger.propagate = True
