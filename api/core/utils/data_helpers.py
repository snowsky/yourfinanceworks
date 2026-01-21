"""
Data Helper Utilities

Common utility functions for data type handling, JSON parsing, and validation.
"""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def ensure_dict(value: Any, field_name: str = "field") -> Dict[str, Any]:
    """
    Ensure a value is a dictionary, handling strings (JSON) and other types.
    
    This is a utility function for safely converting various types to dictionaries,
    with graceful fallback to empty dict on failure.
    
    Args:
        value: Value to convert to dict
        field_name: Name of field for logging purposes
        
    Returns:
        Dictionary, or empty dict if conversion fails
        
    Examples:
        >>> ensure_dict({"key": "value"})
        {"key": "value"}
        
        >>> ensure_dict('{"key": "value"}')
        {"key": "value"}
        
        >>> ensure_dict(None)
        {}
        
        >>> ensure_dict("invalid json")
        {}
    """
    if isinstance(value, dict):
        return value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            else:
                logger.warning(f"Could not parse {field_name}: JSON is not a dict, got {type(parsed).__name__}")
                return {}
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not parse {field_name} as JSON: {e}")
            return {}
    elif value is None:
        return {}
    else:
        logger.warning(f"Unexpected type for {field_name}: {type(value).__name__}, expected dict or JSON string")
        return {}


def ensure_list(value: Any, field_name: str = "field") -> list:
    """
    Ensure a value is a list, handling strings (JSON) and other types.
    
    Args:
        value: Value to convert to list
        field_name: Name of field for logging purposes
        
    Returns:
        List, or empty list if conversion fails
    """
    if isinstance(value, list):
        return value
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            else:
                logger.warning(f"Could not parse {field_name}: JSON is not a list, got {type(parsed).__name__}")
                return []
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not parse {field_name} as JSON: {e}")
            return []
    elif value is None:
        return []
    else:
        logger.warning(f"Unexpected type for {field_name}: {type(value).__name__}, expected list or JSON string")
        return []


def safe_json_loads(text: str, default: Any = None, field_name: str = "field") -> Any:
    """
    Safely parse JSON text with fallback to default value.
    
    Args:
        text: JSON text to parse
        default: Default value if parsing fails
        field_name: Name of field for logging purposes
        
    Returns:
        Parsed JSON object or default value
    """
    if not isinstance(text, str):
        logger.warning(f"Expected string for {field_name}, got {type(text).__name__}")
        return default
    
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Could not parse {field_name} as JSON: {e}")
        return default


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from text that may contain other content.
    
    Attempts to find and parse a JSON object within the text.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Parsed JSON dict if found, None otherwise
    """
    if not isinstance(text, str):
        return None
    
    # Quick path: whole text is JSON
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Try to find JSON object in text
    start_idx = text.find('{')
    if start_idx == -1:
        return None
    
    # Try progressively longer substrings
    for i in range(len(text) - 1, start_idx, -1):
        if text[i] == '}':
            candidate = text[start_idx:i+1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and len(parsed) > 0:
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue
    
    return None


def merge_dicts(*dicts: Dict[str, Any], overwrite: bool = True) -> Dict[str, Any]:
    """
    Merge multiple dictionaries together.
    
    Args:
        *dicts: Variable number of dictionaries to merge
        overwrite: If True, later dicts override earlier ones
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result
