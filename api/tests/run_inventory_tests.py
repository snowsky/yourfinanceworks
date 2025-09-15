#!/usr/bin/env python3
"""
Inventory Management System - Test Runner
Comprehensive test suite for the inventory management system
"""
import subprocess
import sys
import os
from pathlib import Path
import argparse
import time

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

class InventoryTestRunner:
    """Runner for inventory management system tests"""

    def __init__(self):
        self.project_root = project_root
        self.test_dir = project_root / "api" / "tests"
        self.coverage_dir = project_root / "htmlcov"

    def run_command(self, command, description):
        """Run a command and return the result"""
        print(f"\n{'='*60}")
        print(f"🔍 {description}")
        print(f"{'='*60}")
        print(f"Command: {' '.join(command)}")

        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            end_time = time.time()

            print(f"⏱️  Execution time: {end_time - start_time:.2f} seconds")

            if result.returncode == 0:
                print("✅ PASSED"                return True
            else:
                print("❌ FAILED"                print("\nSTDOUT:")
                print(result.stdout)
                print("\nSTDERR:")
                print(result.stderr)
                return False

        except subprocess.TimeoutExpired:
            print("⏰ TIMEOUT - Test took too long")
            return False
        except Exception as e:
            print(f"💥 ERROR: {e}")
            return False

    def run_unit_tests(self):
        """Run unit tests only"""
        return self.run_command([
            "pytest",
            "api/tests/test_inventory_models.py",
            "api/tests/test_inventory_services.py",
            "-v",
            "--tb=short"
        ], "Running Unit Tests (Models & Services)")

    def run_api_tests(self):
        """Run API endpoint tests"""
        return self.run_command([
            "pytest",
            "api/tests/test_inventory_api.py",
            "-v",
            "--tb=short"
        ], "Running API Tests")

    def run_integration_tests(self):
        """Run integration tests"""
        return self.run_command([
            "pytest",
            "api/tests/test_inventory_integration.py",
            "-v",
            "--tb=short"
        ], "Running Integration Tests")

    def run_all_tests(self):
        """Run all inventory tests"""
        return self.run_command([
            "pytest",
            "api/tests/",
            "-v",
            "--tb=short",
            "-x"  # Stop on first failure
        ], "Running All Inventory Tests")

    def run_coverage_tests(self):
        """Run tests with coverage reporting"""
        # Clean up old coverage files
        if self.coverage_dir.exists():
            import shutil
            shutil.rmtree(self.coverage_dir)

        return self.run_command([
            "pytest",
            "api/tests/",
            "--cov=api",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
            "-v"
        ], "Running Tests with Coverage Analysis")

    def run_performance_tests(self):
        """Run performance-focused tests"""
        return self.run_command([
            "pytest",
            "api/tests/",
            "-k", "analytics or report",
            "--durations=10",
            "-v"
        ], "Running Performance Tests (Analytics & Reporting)")

    def check_test_structure(self):
        """Check test file structure and imports"""
        print(f"\n{'='*60}")
        print("🔍 Checking Test Structure")
        print(f"{'='*60}")

        test_files = [
            "api/tests/__init__.py",
            "api/tests/conftest.py",
            "api/tests/test_inventory_models.py",
            "api/tests/test_inventory_services.py",
            "api/tests/test_inventory_api.py",
            "api/tests/test_inventory_integration.py"
        ]

        missing_files = []
        for test_file in test_files:
            if not (self.project_root / test_file).exists():
                missing_files.append(test_file)

        if missing_files:
            print("❌ Missing test files:"            for file in missing_files:
                print(f"   - {file}")
            return False

        print("✅ All test files present")

        # Test imports
        try:
            import pytest
            print("✅ pytest available")

            # Try importing test modules
            test_modules = [
                "tests.conftest",
                "tests.test_inventory_models",
                "tests.test_inventory_services",
                "tests.test_inventory_api",
                "tests.test_inventory_integration"
            ]

            for module in test_modules:
                try:
                    __import__(module)
                    print(f"✅ {module} imports successfully")
                except ImportError as e:
                    print(f"❌ {module} import failed: {e}")
                    return False

        except ImportError:
            print("❌ pytest not available")
            return False

        return True

    def generate_test_report(self):
        """Generate a summary test report"""
        print(f"\n{'='*60}")
        print("📊 Generating Test Report")
        print(f"{'='*60}")

        # Check coverage report
        if self.coverage_dir.exists():
            index_file = self.coverage_dir / "index.html"
            if index_file.exists():
                print(f"📈 Coverage report generated: file://{index_file}")
            else:
                print("❌ Coverage report not found")

        # Count test files and methods
        test_files = list(self.test_dir.glob("test_*.py"))
        print(f"📁 Test files: {len(test_files)}")

        total_tests = 0
        for test_file in test_files:
            try:
                with open(test_file, 'r') as f:
                    content = f.read()
                    # Count test methods (rough estimate)
                    test_count = content.count("def test_")
                    total_tests += test_count
            except Exception:
                pass

        print(f"🧪 Estimated test methods: {total_tests}")

        return True

    def show_help(self):
        """Show available commands"""
        print("""
Inventory Management System - Test Runner

USAGE:
    python api/tests/run_inventory_tests.py [COMMAND]

COMMANDS:
    all              Run all inventory tests
    unit             Run unit tests only (models & services)
    api              Run API endpoint tests
    integration      Run integration tests
    coverage         Run tests with coverage analysis
    performance      Run performance-focused tests
    check            Check test structure and dependencies
    report           Generate test report
    help             Show this help message

EXAMPLES:
    # Run all tests
    python api/tests/run_inventory_tests.py all

    # Run with coverage
    python api/tests/run_inventory_tests.py coverage

    # Check test setup
    python api/tests/run_inventory_tests.py check

TEST STRUCTURE:
    📁 api/tests/
    ├── test_inventory_models.py      # Database model tests
    ├── test_inventory_services.py    # Service layer tests
    ├── test_inventory_api.py         # API endpoint tests
    ├── test_inventory_integration.py # Integration tests
    ├── conftest.py                   # Test configuration
    └── README.md                     # Test documentation
        """)

def main():
    """Main entry point"""
    runner = InventoryTestRunner()

    if len(sys.argv) < 2:
        runner.show_help()
        return

    command = sys.argv[1].lower()

    # Map commands to methods
    command_map = {
        'all': runner.run_all_tests,
        'unit': runner.run_unit_tests,
        'api': runner.run_api_tests,
        'integration': runner.run_integration_tests,
        'coverage': runner.run_coverage_tests,
        'performance': runner.run_performance_tests,
        'check': runner.check_test_structure,
        'report': runner.generate_test_report,
        'help': runner.show_help
    }

    if command in command_map:
        success = command_map[command]()
        if success:
            print(f"\n🎉 {command.title()} completed successfully!")
            sys.exit(0)
        else:
            print(f"\n💥 {command.title()} failed!")
            sys.exit(1)
    else:
        print(f"❌ Unknown command: {command}")
        runner.show_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
