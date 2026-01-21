#!/usr/bin/env python3
"""
OCR Dependencies Setup Script

This script helps set up OCR dependencies and configuration for bank statement processing.
"""

import os
import sys
import subprocess
import platform
import logging
from pathlib import Path

# Add the parent directory to the path so we can import from the API
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from core.utils.dependency_manager import dependency_manager
    from commercial.ai.settings.ocr_config import get_ocr_config, log_ocr_status
except ImportError as e:
    print(f"Warning: Could not import API modules: {e}")
    dependency_manager = None

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def detect_system():
    """Detect the operating system and package manager."""
    system = platform.system().lower()
    
    if system == "linux":
        # Try to detect Linux distribution
        try:
            with open("/etc/os-release", "r") as f:
                content = f.read().lower()
                if "ubuntu" in content or "debian" in content:
                    return "debian"
                elif "centos" in content or "rhel" in content or "red hat" in content:
                    return "rhel"
                elif "fedora" in content:
                    return "fedora"
                elif "alpine" in content:
                    return "alpine"
        except FileNotFoundError:
            pass
        return "linux"
    
    return system


def check_command_available(command):
    """Check if a command is available in PATH."""
    try:
        subprocess.run([command, "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_system_dependencies():
    """Install system dependencies based on the detected OS."""
    system = detect_system()
    
    print(f"Detected system: {system}")
    
    if system == "debian":
        commands = [
            ["sudo", "apt-get", "update"],
            ["sudo", "apt-get", "install", "-y", "tesseract-ocr", "tesseract-ocr-eng"]
        ]
    elif system == "rhel":
        commands = [
            ["sudo", "yum", "install", "-y", "tesseract", "tesseract-langpack-eng"]
        ]
    elif system == "fedora":
        commands = [
            ["sudo", "dnf", "install", "-y", "tesseract", "tesseract-langpack-eng"]
        ]
    elif system == "alpine":
        commands = [
            ["sudo", "apk", "add", "--no-cache", "tesseract-ocr", "tesseract-ocr-data-eng"]
        ]
    elif system == "darwin":  # macOS
        if check_command_available("brew"):
            commands = [["brew", "install", "tesseract"]]
        else:
            print("Homebrew not found. Please install Homebrew first or install Tesseract manually.")
            return False
    else:
        print(f"Unsupported system: {system}")
        print("Please install Tesseract OCR manually:")
        print("- Ubuntu/Debian: sudo apt-get install tesseract-ocr tesseract-ocr-eng")
        print("- CentOS/RHEL: sudo yum install tesseract tesseract-langpack-eng")
        print("- macOS: brew install tesseract")
        print("- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        return False
    
    print("Installing system dependencies...")
    for command in commands:
        try:
            print(f"Running: {' '.join(command)}")
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to run command: {' '.join(command)}")
            print(f"Error: {e}")
            return False
    
    return True


def install_python_dependencies():
    """Install Python dependencies."""
    print("Installing Python dependencies...")
    
    # Check if we're in a virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    if not in_venv:
        print("Warning: Not in a virtual environment. Consider using a virtual environment.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Install OCR-specific dependencies
    dependencies = [
        "unstructured[pdf]==0.18.15",
        "pytesseract==0.3.13",
        "tesseract==0.1.3"
    ]
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.run([sys.executable, "-m", "pip", "install", dep], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {dep}: {e}")
            return False
    
    return True


def setup_configuration():
    """Set up OCR configuration."""
    print("Setting up OCR configuration...")
    
    env_file = Path(__file__).parent.parent / ".env"
    
    # Default configuration
    config_vars = {
        "BANK_OCR_ENABLED": "true",
        "BANK_OCR_TIMEOUT": "300",
        "BANK_OCR_MIN_TEXT_THRESHOLD": "50",
        "BANK_OCR_MIN_WORD_THRESHOLD": "10",
        "TESSERACT_CMD": "/usr/bin/tesseract",
        "TESSERACT_CONFIG": "--oem 3 --psm 6",
        "UNSTRUCTURED_STRATEGY": "hi_res",
        "UNSTRUCTURED_MODE": "single",
        "UNSTRUCTURED_USE_API": "false"
    }
    
    # Check if .env file exists
    if env_file.exists():
        print(f"Found existing .env file: {env_file}")
        
        # Read existing content
        with open(env_file, "r") as f:
            existing_content = f.read()
        
        # Check which variables are already set
        existing_vars = set()
        for line in existing_content.split('\n'):
            if '=' in line and not line.strip().startswith('#'):
                var_name = line.split('=')[0].strip()
                existing_vars.add(var_name)
        
        # Only add missing variables
        new_vars = {}
        for var, value in config_vars.items():
            if var not in existing_vars:
                new_vars[var] = value
        
        if new_vars:
            print(f"Adding {len(new_vars)} new OCR configuration variables to .env")
            with open(env_file, "a") as f:
                f.write("\n# OCR Configuration (added by setup script)\n")
                for var, value in new_vars.items():
                    f.write(f"{var}={value}\n")
        else:
            print("All OCR configuration variables already present in .env")
    
    else:
        print(f"Creating new .env file: {env_file}")
        with open(env_file, "w") as f:
            f.write("# OCR Configuration\n")
            for var, value in config_vars.items():
                f.write(f"{var}={value}\n")
    
    return True


def test_installation():
    """Test the OCR installation."""
    print("Testing OCR installation...")
    
    # Test Tesseract
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✓ Tesseract: {version}")
        else:
            print("✗ Tesseract: Command failed")
            return False
    except FileNotFoundError:
        print("✗ Tesseract: Not found in PATH")
        return False
    
    # Test Python packages
    packages = ["unstructured", "pytesseract"]
    for package in packages:
        try:
            if package == "unstructured":
                import unstructured
                from unstructured.partition.pdf import partition_pdf
                print(f"✓ {package}: {getattr(unstructured, '__version__', 'unknown')}")
            elif package == "pytesseract":
                import pytesseract
                print(f"✓ {package}: {getattr(pytesseract, '__version__', 'unknown')}")
        except ImportError:
            print(f"✗ {package}: Not available")
            return False
    
    # Test with dependency manager if available
    if dependency_manager:
        print("\nRunning comprehensive dependency check...")
        try:
            report = dependency_manager.generate_dependency_report()
            ocr_available = dependency_manager.is_feature_available("ocr")
            print(f"OCR Feature Available: {'✓' if ocr_available else '✗'}")
            
            if not ocr_available:
                instructions = dependency_manager.get_installation_instructions("ocr")
                if instructions.get("missing_dependencies"):
                    print("Missing dependencies:")
                    for dep in instructions["missing_dependencies"]:
                        print(f"  - {dep['name']}: {dep['description']}")
        except Exception as e:
            print(f"Dependency manager test failed: {e}")
    
    return True


def main():
    """Main setup function."""
    print("OCR Dependencies Setup Script")
    print("=" * 40)
    
    # Check if running as root (not recommended)
    if os.geteuid() == 0:
        print("Warning: Running as root is not recommended.")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return 1
    
    steps = [
        ("Installing system dependencies", install_system_dependencies),
        ("Installing Python dependencies", install_python_dependencies),
        ("Setting up configuration", setup_configuration),
        ("Testing installation", test_installation)
    ]
    
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        try:
            if not step_func():
                print(f"Failed: {step_name}")
                return 1
        except KeyboardInterrupt:
            print("\nSetup interrupted by user")
            return 1
        except Exception as e:
            print(f"Error during {step_name}: {e}")
            return 1
    
    print("\n" + "=" * 40)
    print("OCR setup completed successfully!")
    print("\nNext steps:")
    print("1. Restart your application to load the new configuration")
    print("2. Test OCR functionality with a sample bank statement")
    print("3. Check the logs for any OCR-related messages")
    print("\nFor troubleshooting, see: api/docs/OCR_INSTALLATION_GUIDE.md")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())