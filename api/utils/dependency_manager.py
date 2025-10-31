"""
Dependency Manager for OCR and other optional features

This module provides comprehensive dependency checking and graceful fallback
when optional dependencies are not available.
"""

import os
import sys
import logging
import subprocess
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """Status of a dependency."""
    AVAILABLE = "available"
    MISSING = "missing"
    OUTDATED = "outdated"
    ERROR = "error"


@dataclass
class DependencyInfo:
    """Information about a dependency."""
    name: str
    type: str  # "python", "system", "api"
    required: bool
    status: DependencyStatus
    version: Optional[str] = None
    min_version: Optional[str] = None
    error_message: Optional[str] = None
    install_command: Optional[str] = None
    description: Optional[str] = None


class DependencyManager:
    """Manages dependency checking and graceful fallback."""
    
    def __init__(self):
        self.dependencies = {}
        self._register_ocr_dependencies()
    
    def _register_ocr_dependencies(self):
        """Register OCR-related dependencies."""
        self.dependencies.update({
            # Python packages
            "unstructured": DependencyInfo(
                name="unstructured",
                type="python",
                required=False,
                status=DependencyStatus.MISSING,
                min_version="0.10.0",
                install_command="pip install unstructured[pdf]",
                description="UnstructuredLoader for document processing"
            ),

            "pytesseract": DependencyInfo(
                name="pytesseract",
                type="python",
                required=False,
                status=DependencyStatus.MISSING,
                min_version="0.3.0",
                install_command="pip install pytesseract",
                description="Python wrapper for Tesseract OCR"
            ),
            
            # System dependencies
            "tesseract": DependencyInfo(
                name="tesseract",
                type="system",
                required=False,
                status=DependencyStatus.MISSING,
                install_command="sudo apt-get install tesseract-ocr",
                description="Tesseract OCR engine"
            ),
            
            # API dependencies
            "unstructured_api": DependencyInfo(
                name="unstructured_api",
                type="api",
                required=False,
                status=DependencyStatus.MISSING,
                description="Unstructured.io API access"
            )
        })
    
    def check_all_dependencies(self) -> Dict[str, DependencyInfo]:
        """Check status of all registered dependencies."""
        for name, dep_info in self.dependencies.items():
            if dep_info.type == "python":
                self._check_python_dependency(dep_info)
            elif dep_info.type == "system":
                self._check_system_dependency(dep_info)
            elif dep_info.type == "api":
                self._check_api_dependency(dep_info)
        
        return self.dependencies.copy()
    
    def _check_python_dependency(self, dep_info: DependencyInfo):
        """Check Python package dependency."""
        try:
            if dep_info.name == "unstructured":
                import unstructured
                dep_info.version = getattr(unstructured, '__version__', 'unknown')
                dep_info.status = DependencyStatus.AVAILABLE
                

                
            elif dep_info.name == "pytesseract":
                import pytesseract
                dep_info.version = getattr(pytesseract, '__version__', 'unknown')
                dep_info.status = DependencyStatus.AVAILABLE
                
        except ImportError as e:
            dep_info.status = DependencyStatus.MISSING
            dep_info.error_message = f"Import failed: {e}"
        except Exception as e:
            dep_info.status = DependencyStatus.ERROR
            dep_info.error_message = f"Unexpected error: {e}"
    
    def _check_system_dependency(self, dep_info: DependencyInfo):
        """Check system binary dependency."""
        try:
            if dep_info.name == "tesseract":
                # Check if tesseract command is available
                result = subprocess.run(
                    ["tesseract", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    # Extract version from output
                    version_line = result.stdout.split('\n')[0]
                    if 'tesseract' in version_line.lower():
                        dep_info.version = version_line.split()[-1] if version_line.split() else 'unknown'
                    dep_info.status = DependencyStatus.AVAILABLE
                else:
                    dep_info.status = DependencyStatus.ERROR
                    dep_info.error_message = f"Command failed: {result.stderr}"
                    
        except FileNotFoundError:
            dep_info.status = DependencyStatus.MISSING
            dep_info.error_message = "Binary not found in PATH"
        except subprocess.TimeoutExpired:
            dep_info.status = DependencyStatus.ERROR
            dep_info.error_message = "Command timed out"
        except Exception as e:
            dep_info.status = DependencyStatus.ERROR
            dep_info.error_message = f"Unexpected error: {e}"
    
    def _check_api_dependency(self, dep_info: DependencyInfo):
        """Check API dependency."""
        if dep_info.name == "unstructured_api":
            api_key = os.getenv("UNSTRUCTURED_API_KEY")
            if api_key:
                dep_info.status = DependencyStatus.AVAILABLE
                dep_info.version = "configured"
            else:
                dep_info.status = DependencyStatus.MISSING
                dep_info.error_message = "API key not configured"
    
    def get_missing_dependencies(self) -> List[DependencyInfo]:
        """Get list of missing dependencies."""
        self.check_all_dependencies()
        return [dep for dep in self.dependencies.values() 
                if dep.status == DependencyStatus.MISSING]
    
    def get_available_dependencies(self) -> List[DependencyInfo]:
        """Get list of available dependencies."""
        self.check_all_dependencies()
        return [dep for dep in self.dependencies.values() 
                if dep.status == DependencyStatus.AVAILABLE]
    
    def is_feature_available(self, feature: str) -> bool:
        """Check if a feature is available based on its dependencies."""
        if feature == "ocr":
            return self._is_ocr_available()
        return False
    
    def _is_ocr_available(self) -> bool:
        """Check if OCR functionality is available."""
        self.check_all_dependencies()
        
        # Need unstructured
        has_unstructured = (
            self.dependencies["unstructured"].status == DependencyStatus.AVAILABLE
        )
        
        # For local processing, also need pytesseract and tesseract
        has_local_ocr = (
            self.dependencies["pytesseract"].status == DependencyStatus.AVAILABLE and
            self.dependencies["tesseract"].status == DependencyStatus.AVAILABLE
        )
        
        # For API processing, need API key
        has_api_ocr = self.dependencies["unstructured_api"].status == DependencyStatus.AVAILABLE
        
        # OCR is available if we have unstructured AND (local OR API)
        return has_unstructured and (has_local_ocr or has_api_ocr)
    
    def get_installation_instructions(self, feature: str) -> Dict[str, Any]:
        """Get installation instructions for a feature."""
        if feature == "ocr":
            return self._get_ocr_installation_instructions()
        return {}
    
    def _get_ocr_installation_instructions(self) -> Dict[str, Any]:
        """Get OCR installation instructions."""
        missing = self.get_missing_dependencies()
        ocr_missing = [dep for dep in missing if dep.name in 
                      ["unstructured", "pytesseract", "tesseract"]]
        
        instructions = {
            "feature": "OCR",
            "available": self.is_feature_available("ocr"),
            "missing_dependencies": [],
            "installation_steps": []
        }
        
        for dep in ocr_missing:
            instructions["missing_dependencies"].append({
                "name": dep.name,
                "type": dep.type,
                "description": dep.description,
                "install_command": dep.install_command
            })
        
        # Generate installation steps
        python_deps = [dep for dep in ocr_missing if dep.type == "python"]
        system_deps = [dep for dep in ocr_missing if dep.type == "system"]
        
        if system_deps:
            instructions["installation_steps"].append({
                "step": 1,
                "title": "Install system dependencies",
                "commands": [dep.install_command for dep in system_deps if dep.install_command],
                "description": "Install required system packages"
            })
        
        if python_deps:
            instructions["installation_steps"].append({
                "step": 2,
                "title": "Install Python packages",
                "commands": [dep.install_command for dep in python_deps if dep.install_command],
                "description": "Install required Python packages"
            })
        
        # Add configuration step
        instructions["installation_steps"].append({
            "step": 3,
            "title": "Configure environment",
            "commands": ["# Add to .env file:", "BANK_OCR_ENABLED=true"],
            "description": "Enable OCR functionality in configuration"
        })
        
        return instructions
    
    def generate_dependency_report(self) -> Dict[str, Any]:
        """Generate comprehensive dependency report."""
        self.check_all_dependencies()
        
        report = {
            "timestamp": logger.handlers[0].formatter.formatTime(
                logger.makeRecord("dependency_manager", logging.INFO, "", 0, "", (), None)
            ) if logger.handlers else "unknown",
            "python_version": sys.version,
            "platform": sys.platform,
            "dependencies": {},
            "features": {},
            "summary": {
                "total": len(self.dependencies),
                "available": 0,
                "missing": 0,
                "errors": 0
            }
        }
        
        # Process dependencies
        for name, dep in self.dependencies.items():
            report["dependencies"][name] = {
                "name": dep.name,
                "type": dep.type,
                "status": dep.status.value,
                "version": dep.version,
                "required": dep.required,
                "error_message": dep.error_message,
                "description": dep.description
            }
            
            # Update summary
            if dep.status == DependencyStatus.AVAILABLE:
                report["summary"]["available"] += 1
            elif dep.status == DependencyStatus.MISSING:
                report["summary"]["missing"] += 1
            else:
                report["summary"]["errors"] += 1
        
        # Check features
        report["features"]["ocr"] = {
            "available": self.is_feature_available("ocr"),
            "dependencies": ["unstructured", "pytesseract", "tesseract"],
            "installation_guide": "See api/docs/OCR_INSTALLATION_GUIDE.md"
        }
        
        return report
    
    def log_dependency_status(self):
        """Log dependency status for debugging."""
        report = self.generate_dependency_report()
        
        logger.info(f"Dependency Check Summary: {report['summary']['available']}/{report['summary']['total']} available")
        
        for name, dep in report["dependencies"].items():
            if dep["status"] == "available":
                logger.debug(f"✓ {name} ({dep['version'] or 'unknown version'})")
            elif dep["status"] == "missing":
                logger.warning(f"✗ {name} - {dep['error_message'] or 'not available'}")
            else:
                logger.error(f"! {name} - {dep['error_message'] or 'error'}")
        
        # Log feature availability
        for feature, info in report["features"].items():
            status = "available" if info["available"] else "unavailable"
            logger.info(f"Feature '{feature}': {status}")


# Global instance
dependency_manager = DependencyManager()


# Convenience functions
def check_ocr_dependencies() -> Dict[str, bool]:
    """Check OCR dependencies (backward compatibility)."""
    deps = dependency_manager.check_all_dependencies()
    return {
        "unstructured": deps["unstructured"].status == DependencyStatus.AVAILABLE,
        "pytesseract": deps["pytesseract"].status == DependencyStatus.AVAILABLE,
        "tesseract_binary": deps["tesseract"].status == DependencyStatus.AVAILABLE
    }


def is_ocr_available() -> bool:
    """Check if OCR functionality is available (backward compatibility)."""
    return dependency_manager.is_feature_available("ocr")


def get_ocr_installation_guide() -> Dict[str, Any]:
    """Get OCR installation instructions."""
    return dependency_manager.get_installation_instructions("ocr")


def log_dependency_status():
    """Log dependency status."""
    dependency_manager.log_dependency_status()