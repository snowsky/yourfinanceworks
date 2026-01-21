"""
OCR Configuration Management

This module provides configuration management for OCR operations
including environment variable handling, validation, and admin controls.
"""

import os
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from commercial.ai.exceptions.bank_ocr_exceptions import OCRConfigurationError

logger = logging.getLogger(__name__)


@dataclass
class OCRConfig:
    """Configuration class for OCR operations."""
    
    # Core OCR settings
    enabled: bool = True
    timeout_seconds: int = 300
    min_text_threshold: int = 50
    min_word_threshold: int = 10
    
    # UnstructuredLoader settings
    use_unstructured_api: bool = False
    unstructured_api_key: Optional[str] = None
    unstructured_api_url: Optional[str] = None
    
    # Tesseract settings
    tesseract_cmd: Optional[str] = None
    tesseract_config: Optional[str] = None
    
    # Processing settings
    strategy: str = "hi_res"
    mode: str = "single"
    
    @classmethod
    def from_environment(cls) -> 'OCRConfig':
        """Create OCR configuration from environment variables."""
        try:
            return cls(
                enabled=_get_bool_env("BANK_OCR_ENABLED", True),
                timeout_seconds=_get_int_env("BANK_OCR_TIMEOUT", 300),
                min_text_threshold=_get_int_env("BANK_OCR_MIN_TEXT_THRESHOLD", 50),
                min_word_threshold=_get_int_env("BANK_OCR_MIN_WORD_THRESHOLD", 10),
                
                use_unstructured_api=_get_bool_env("UNSTRUCTURED_USE_API", False),
                unstructured_api_key=os.getenv("UNSTRUCTURED_API_KEY"),
                unstructured_api_url=os.getenv("UNSTRUCTURED_API_URL", "https://api.unstructured.io"),
                
                tesseract_cmd=os.getenv("TESSERACT_CMD"),
                tesseract_config=os.getenv("TESSERACT_CONFIG", "--oem 3 --psm 6"),
                
                strategy=os.getenv("UNSTRUCTURED_STRATEGY", "hi_res"),
                mode=os.getenv("UNSTRUCTURED_MODE", "single")
            )
        except Exception as e:
            raise OCRConfigurationError(
                f"Failed to load OCR configuration from environment: {e}",
                details={"error": str(e)}
            )
    
    def validate(self) -> None:
        """Validate the OCR configuration."""
        errors = []
        
        if self.timeout_seconds <= 0:
            errors.append("timeout_seconds must be positive")
        
        if self.min_text_threshold < 0:
            errors.append("min_text_threshold must be non-negative")
        
        if self.min_word_threshold < 0:
            errors.append("min_word_threshold must be non-negative")
        
        if self.use_unstructured_api and not self.unstructured_api_key:
            errors.append("unstructured_api_key is required when use_unstructured_api is True")
        
        if self.strategy not in ["hi_res", "fast", "ocr_only", "auto"]:
            errors.append(f"Invalid strategy: {self.strategy}")
        
        if self.mode not in ["single", "elements", "paged"]:
            errors.append(f"Invalid mode: {self.mode}")
        
        if errors:
            raise OCRConfigurationError(
                f"OCR configuration validation failed: {'; '.join(errors)}",
                details={"validation_errors": errors}
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "enabled": self.enabled,
            "timeout_seconds": self.timeout_seconds,
            "min_text_threshold": self.min_text_threshold,
            "min_word_threshold": self.min_word_threshold,
            "use_unstructured_api": self.use_unstructured_api,
            "unstructured_api_key": "***" if self.unstructured_api_key else None,
            "unstructured_api_url": self.unstructured_api_url,
            "tesseract_cmd": self.tesseract_cmd,
            "tesseract_config": self.tesseract_config,
            "strategy": self.strategy,
            "mode": self.mode
        }
    
    def to_admin_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for admin display (includes sensitive data)."""
        config_dict = asdict(self)
        # Mark sensitive fields for admin view
        if config_dict.get("unstructured_api_key"):
            config_dict["unstructured_api_key_masked"] = "***" + config_dict["unstructured_api_key"][-4:] if len(config_dict["unstructured_api_key"]) > 4 else "***"
        return config_dict
    
    def update_from_dict(self, updates: Dict[str, Any]) -> None:
        """Update configuration from dictionary (for admin updates)."""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Re-validate after updates
        self.validate()


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer value for {key}: {value}, using default {default}")
        return default


def get_ocr_config() -> OCRConfig:
    """Get validated OCR configuration."""
    config = OCRConfig.from_environment()
    config.validate()
    return config


def check_ocr_dependencies() -> Dict[str, bool]:
    """Check availability of OCR dependencies."""
    # Use the new dependency manager for more robust checking
    try:
        from core.utils.dependency_manager import dependency_manager
        deps = dependency_manager.check_all_dependencies()
        
        return {
            "unstructured": deps["unstructured"].status.value == "available",
            "pytesseract": deps["pytesseract"].status.value == "available",
            "tesseract_binary": deps["tesseract"].status.value == "available"
        }
    except ImportError:
        # Fallback to basic checking if dependency manager not available
        logger.warning("Dependency manager not available, using basic dependency checking")
        return _check_ocr_dependencies_basic()


def _check_ocr_dependencies_basic() -> Dict[str, bool]:
    """Basic OCR dependency checking (fallback)."""
    dependencies = {
        "unstructured": False,
        "pytesseract": False,
        "tesseract_binary": False
    }
    
    # Check unstructured
    try:
        import unstructured
        dependencies["unstructured"] = True
        logger.debug("unstructured package available")
    except ImportError:
        logger.debug("unstructured package not available")
    
    # Check pytesseract
    try:
        import pytesseract
        dependencies["pytesseract"] = True
        logger.debug("pytesseract package available")
    except ImportError:
        logger.debug("pytesseract package not available")
    
    # Check tesseract binary
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        dependencies["tesseract_binary"] = True
        logger.debug("tesseract binary available")
    except Exception:
        logger.debug("tesseract binary not available")
    
    return dependencies


def is_ocr_available() -> bool:
    """Check if OCR functionality is available."""
    try:
        from core.utils.dependency_manager import dependency_manager
        return dependency_manager.is_feature_available("ocr")
    except ImportError:
        # Fallback to basic checking
        deps = check_ocr_dependencies()
        
        # Need either unstructured API or local tesseract
        has_unstructured = deps["unstructured"]
        has_tesseract = deps["pytesseract"] and deps["tesseract_binary"]
        
        config = get_ocr_config()
        
        if config.use_unstructured_api:
            return has_unstructured and bool(config.unstructured_api_key)
        else:
            return has_unstructured and has_tesseract


def log_ocr_status() -> None:
    """Log OCR configuration and dependency status."""
    try:
        config = get_ocr_config()
        deps = check_ocr_dependencies()
        available = is_ocr_available()
        
        logger.info(f"OCR Status: {'Available' if available else 'Unavailable'}")
        logger.info(f"OCR Enabled: {config.enabled}")
        logger.info(f"OCR Dependencies: {deps}")
        
        if config.enabled and not available:
            logger.warning("OCR is enabled but dependencies are not available")
        
    except Exception as e:
        logger.error(f"Failed to check OCR status: {e}")


# Admin Control Functions

def get_ocr_admin_status() -> Dict[str, Any]:
    """Get comprehensive OCR status for admin interface."""
    try:
        config = get_ocr_config()
        deps = check_ocr_dependencies()
        available = is_ocr_available()
        
        return {
            "status": "available" if available else "unavailable",
            "enabled": config.enabled,
            "configuration": config.to_admin_dict(),
            "dependencies": deps,
            "dependency_status": {
                "unstructured_available": deps["unstructured"],
                "tesseract_available": deps["pytesseract"] and deps["tesseract_binary"],
                "api_configured": bool(config.unstructured_api_key) if config.use_unstructured_api else True,
                "local_configured": deps["pytesseract"] and deps["tesseract_binary"]
            },
            "warnings": _get_configuration_warnings(config, deps, available)
        }
    except Exception as e:
        return {
            "status": "error",
            "enabled": False,
            "error": str(e),
            "configuration": {},
            "dependencies": {},
            "dependency_status": {},
            "warnings": [f"Failed to load OCR configuration: {e}"]
        }


def update_ocr_config_admin(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update OCR configuration (admin function)."""
    try:
        # Load current config
        config = get_ocr_config()
        
        # Validate updates
        _validate_admin_updates(updates)
        
        # Apply updates
        config.update_from_dict(updates)
        
        # Log the configuration change
        logger.info(f"OCR configuration updated by admin: {list(updates.keys())}")
        
        # Return updated status
        return get_ocr_admin_status()
        
    except Exception as e:
        logger.error(f"Failed to update OCR configuration: {e}")
        raise OCRConfigurationError(
            f"Failed to update OCR configuration: {e}",
            details={"updates": updates, "error": str(e)}
        )


def disable_ocr_admin(reason: str = "Disabled by administrator") -> Dict[str, Any]:
    """Disable OCR functionality (admin function)."""
    try:
        # Set environment variable to disable OCR
        os.environ["BANK_OCR_ENABLED"] = "false"
        
        logger.warning(f"OCR disabled by admin: {reason}")
        
        return {
            "status": "disabled",
            "message": f"OCR functionality has been disabled: {reason}",
            "timestamp": logger.handlers[0].formatter.formatTime(logger.makeRecord(
                "ocr_config", logging.INFO, "", 0, "", (), None
            )) if logger.handlers else None
        }
        
    except Exception as e:
        logger.error(f"Failed to disable OCR: {e}")
        raise OCRConfigurationError(f"Failed to disable OCR: {e}")


def enable_ocr_admin(reason: str = "Enabled by administrator") -> Dict[str, Any]:
    """Enable OCR functionality (admin function)."""
    try:
        # Check if dependencies are available
        deps = check_ocr_dependencies()
        if not deps["unstructured"]:
            raise OCRConfigurationError(
                "Cannot enable OCR: Required dependencies not available",
                details={"missing_dependencies": [k for k, v in deps.items() if not v]}
            )
        
        # Set environment variable to enable OCR
        os.environ["BANK_OCR_ENABLED"] = "true"
        
        logger.info(f"OCR enabled by admin: {reason}")
        
        return {
            "status": "enabled",
            "message": f"OCR functionality has been enabled: {reason}",
            "configuration": get_ocr_config().to_admin_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to enable OCR: {e}")
        raise OCRConfigurationError(f"Failed to enable OCR: {e}")


def test_ocr_configuration() -> Dict[str, Any]:
    """Test OCR configuration and dependencies."""
    try:
        config = get_ocr_config()
        deps = check_ocr_dependencies()
        
        test_results = {
            "configuration_valid": True,
            "dependencies_available": is_ocr_available(),
            "tests": {}
        }
        
        # Test configuration validation
        try:
            config.validate()
            test_results["tests"]["configuration_validation"] = {
                "status": "pass",
                "message": "Configuration validation successful"
            }
        except Exception as e:
            test_results["configuration_valid"] = False
            test_results["tests"]["configuration_validation"] = {
                "status": "fail",
                "message": f"Configuration validation failed: {e}"
            }
        
        # Test dependency availability
        for dep_name, available in deps.items():
            test_results["tests"][f"dependency_{dep_name}"] = {
                "status": "pass" if available else "fail",
                "message": f"{dep_name} is {'available' if available else 'not available'}"
            }
        
        # Test API configuration if using Unstructured API
        if config.use_unstructured_api:
            if config.unstructured_api_key:
                test_results["tests"]["api_configuration"] = {
                    "status": "pass",
                    "message": "API key configured"
                }
            else:
                test_results["tests"]["api_configuration"] = {
                    "status": "fail",
                    "message": "API key not configured"
                }
        
        return test_results
        
    except Exception as e:
        return {
            "configuration_valid": False,
            "dependencies_available": False,
            "error": str(e),
            "tests": {
                "overall": {
                    "status": "fail",
                    "message": f"Test failed: {e}"
                }
            }
        }


def _validate_admin_updates(updates: Dict[str, Any]) -> None:
    """Validate admin configuration updates."""
    allowed_fields = {
        "enabled", "timeout_seconds", "min_text_threshold", "min_word_threshold",
        "use_unstructured_api", "unstructured_api_key", "unstructured_api_url",
        "tesseract_cmd", "tesseract_config", "strategy", "mode"
    }
    
    invalid_fields = set(updates.keys()) - allowed_fields
    if invalid_fields:
        raise OCRConfigurationError(
            f"Invalid configuration fields: {invalid_fields}",
            details={"invalid_fields": list(invalid_fields), "allowed_fields": list(allowed_fields)}
        )
    
    # Validate specific field types and values
    if "timeout_seconds" in updates and (not isinstance(updates["timeout_seconds"], int) or updates["timeout_seconds"] <= 0):
        raise OCRConfigurationError("timeout_seconds must be a positive integer")
    
    if "min_text_threshold" in updates and (not isinstance(updates["min_text_threshold"], int) or updates["min_text_threshold"] < 0):
        raise OCRConfigurationError("min_text_threshold must be a non-negative integer")
    
    if "min_word_threshold" in updates and (not isinstance(updates["min_word_threshold"], int) or updates["min_word_threshold"] < 0):
        raise OCRConfigurationError("min_word_threshold must be a non-negative integer")
    
    if "strategy" in updates and updates["strategy"] not in ["hi_res", "fast", "ocr_only", "auto"]:
        raise OCRConfigurationError(f"Invalid strategy: {updates['strategy']}")
    
    if "mode" in updates and updates["mode"] not in ["single", "elements", "paged"]:
        raise OCRConfigurationError(f"Invalid mode: {updates['mode']}")


def _get_configuration_warnings(config: OCRConfig, deps: Dict[str, bool], available: bool) -> List[str]:
    """Get configuration warnings for admin interface."""
    warnings = []
    
    if config.enabled and not available:
        warnings.append("OCR is enabled but dependencies are not available")
    
    if config.use_unstructured_api and not config.unstructured_api_key:
        warnings.append("Unstructured API is enabled but no API key is configured")
    
    if not config.use_unstructured_api and not (deps.get("pytesseract") and deps.get("tesseract_binary")):
        warnings.append("Local Tesseract is configured but not available")
    
    if config.timeout_seconds > 600:
        warnings.append("OCR timeout is very high (>10 minutes), consider reducing for better user experience")
    
    if config.min_text_threshold < 10:
        warnings.append("Text threshold is very low, may trigger OCR unnecessarily")
    
    return warnings


def get_ocr_environment_template() -> Dict[str, str]:
    """Get template of OCR environment variables for documentation."""
    return {
        "BANK_OCR_ENABLED": "true",
        "BANK_OCR_TIMEOUT": "300",
        "BANK_OCR_MIN_TEXT_THRESHOLD": "50",
        "BANK_OCR_MIN_WORD_THRESHOLD": "10",
        "UNSTRUCTURED_USE_API": "false",
        "UNSTRUCTURED_API_KEY": "your-unstructured-api-key-here",
        "UNSTRUCTURED_API_URL": "https://api.unstructured.io",
        "TESSERACT_CMD": "/usr/bin/tesseract",
        "TESSERACT_CONFIG": "--oem 3 --psm 6",
        "UNSTRUCTURED_STRATEGY": "hi_res",
        "UNSTRUCTURED_MODE": "single"
    }