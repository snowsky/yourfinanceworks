"""
Password validation utilities.
"""

import re
from typing import List, Tuple

from core.constants.password import MIN_PASSWORD_LENGTH, PASSWORD_COMPLEXITY


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength based on configured requirements.
    
    Args:
        password: The password to validate
        
    Returns:
        Tuple of (is_valid, list_of_error_messages)
    """
    errors = []
    
    # Check minimum length
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
    
    # Check complexity requirements
    if PASSWORD_COMPLEXITY["require_uppercase"] and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    if PASSWORD_COMPLEXITY["require_lowercase"] and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    if PASSWORD_COMPLEXITY["require_numbers"] and not re.search(r'\d', password):
        errors.append("Password must contain at least one number")
    
    if PASSWORD_COMPLEXITY["require_special_chars"]:
        special_chars_pattern = f"[{re.escape(PASSWORD_COMPLEXITY['special_chars'])}]"
        if not re.search(special_chars_pattern, password):
            errors.append(f"Password must contain at least one special character ({PASSWORD_COMPLEXITY['special_chars']})")
    
    return len(errors) == 0, errors


def get_password_requirements() -> List[str]:
    """
    Get a list of password requirements for display to users.
    
    Returns:
        List of requirement strings
    """
    requirements = [f"At least {MIN_PASSWORD_LENGTH} characters long"]
    
    if PASSWORD_COMPLEXITY["require_uppercase"]:
        requirements.append("At least one uppercase letter")
    
    if PASSWORD_COMPLEXITY["require_lowercase"]:
        requirements.append("At least one lowercase letter")
    
    if PASSWORD_COMPLEXITY["require_numbers"]:
        requirements.append("At least one number")
    
    if PASSWORD_COMPLEXITY["require_special_chars"]:
        requirements.append(f"At least one special character ({PASSWORD_COMPLEXITY['special_chars']})")
    
    return requirements
