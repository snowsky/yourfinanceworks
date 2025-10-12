#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for Reporting Module

This script runs the complete test suite for the reporting module,
including unit tests, integration tests, performance tests, and security tests.

Usage:
    python run_comprehensive_tests.py [options]

Options:
    --quick         Run only essential tests (faster execution)
    --performance   Run performance benchmarks
    --security      Run security tests
    --integration   Run integration tests
    --all          Run all tests (default)
    --verbose      Verbose output
    --parallel     Run tests in parallel (if pytest-xdist is available)

Requirements covered: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Any
import time

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


class ComprehensiveTestRunner:
    """Runner for the comprehensive reporting test suite"""
    
    def __init__(self, args):
        self.args = args
        self.test_dir = Path(__file__).parent / "tests"
        self.results = {}
    
    def run(self) -> bool:
        """Run the comprehensive test suite"""
        print("🚀 Starting Comprehensive Reporting Module Test Suite")
        print("=" * 60)
        
        start_time = time.time()
        
        try:
            if self.args.all or (not any([self.args.quick, self.args.performance, 
                                        self.args.security, self.args.integration])):
                success = self._run_all_tests()
            else:
                success = self._run_selected_tests()
            
            execution_time = time.time() - start_time
            
            print("\n" + "=" * 60)
            print(f"⏱️  Total execution time: {execution_time:.1f} seconds")
            
            if success:
                print("🎉 ALL TESTS PASSED! Reporting module is ready.")
                return True
            else:
                print("❌ Some tests failed. Please review and fix issues.")
                return False
                
        except KeyboardInterrupt:
            print("\n⚠️  Test execution interrupted by user")
            return False
        except Exception as e:
            print(f"\n💥 Test execution failed with error: {e}")
            return False
    
    def _run_all_tests(self) -> bool:
        """Run all test categories"""
        test_categories = [
            ("Unit Tests", self._run_unit_tests),
            ("Integration Tests", self._run_integration_tests),
            ("Performance Tests", self._run_performance_tests),
            ("Security Tests", self._run_security_tests),
            ("End-to-End Tests", self._run_e2e_tests),
        ]
        
        all_passed = True
        
        for category_name, test_function in test_categories:
            print(f"\n📋 Running {category_name}...")
            
            try:
                passed = test_function()
                if passed:
                    print(f"✅ {category_name} completed successfully")
                else:
                    print(f"❌ {category_name} failed")
                    all_passed = False
            except Exception as e:
                print(f"💥 {category_name} failed with error: {e}")
                all_passed = False
        
        return all_passed
    
    def _run_selected_tests(self) -> bool:
        """Run only selected test categories"""
        all_passed = True
        
        if self.args.quick:
            print("\n⚡ Running Quick Test Suite...")
            all_passed &= self._run_essential_tests()
        
        if self.args.integration:
            print("\n🔗 Running Integration Tests...")
            all_passed &= self._run_integration_tests()
        
        if self.args.performance:
            print("\n⚡ Running Performance Tests...")
            all_passed &= self._run_performance_tests()
        
        if self.args.security:
            print("\n🔒 Running Security Tests...")
            all_passed &= self._run_security_tests()
        
        return all_passed
    
    def _run_unit_tests(self) -> bool:
        """Run unit tests for reporting components"""
        unit_test_files = [
            "test_report_service.py",
            "test_report_data_aggregator.py", 
            "test_report_exporter.py",
            "test_report_template_service.py",
            "test_report_scheduler.py",
            "test_report_validation_service.py",
            "test_report_retry_service.py",
            "test_report_error_handling.py",
            "test_report_cleanup_service.py",
            "test_report_history_service.py"
        ]
        
        return self._run_pytest_files(unit_test_files, "Unit Tests")
    
    def _run_integration_tests(self) -> bool:
        """Run integration tests"""
        integration_test_files = [
            "test_reporting_integration.py",
            "test_reporting_integration_simple.py",
            "test_report_data_aggregator_integration.py",
            "test_report_template_integration.py",
            "test_report_scheduler_integration.py"
        ]
        
        return self._run_pytest_files(integration_test_files, "Integration Tests")
    
    def _run_performance_tests(self) -> bool:
        """Run performance and benchmark tests"""
        performance_test_files = [
            "test_report_performance.py",
            "test_reporting_performance_benchmarks.py"
        ]
        
        # Performance tests may take longer
        return self._run_pytest_files(
            performance_test_files, 
            "Performance Tests",
            timeout=600,  # 10 minutes
            additional_args=["-s"]  # Show output for performance metrics
        )
    
    def _run_security_tests(self) -> bool:
        """Run security and access control tests"""
        security_test_files = [
            "test_report_security.py",
            "test_report_audit_logging.py"
        ]
        
        return self._run_pytest_files(security_test_files, "Security Tests")
    
    def _run_e2e_tests(self) -> bool:
        """Run end-to-end workflow tests"""
        e2e_test_files = [
            "test_end_to_end_reporting.py",
            "test_comprehensive_reporting_suite.py"
        ]
        
        return self._run_pytest_files(
            e2e_test_files, 
            "End-to-End Tests",
            timeout=300  # 5 minutes
        )
    
    def _run_essential_tests(self) -> bool:
        """Run essential tests for quick validation"""
        essential_test_files = [
            "test_report_service.py",
            "test_report_data_aggregator.py",
            "test_report_exporter.py",
            "test_reporting_integration_simple.py"
        ]
        
        return self._run_pytest_files(essential_test_files, "Essential Tests")
    
    def _run_pytest_files(self, test_files: List[str], category_name: str, 
                         timeout: int = 120, additional_args: List[str] = None) -> bool:
        """Run pytest on a list of test files"""
        
        existing_files = []
        missing_files = []
        
        for test_file in test_files:
            test_path = self.test_dir / test_file
            if test_path.exists():
                existing_files.append(str(test_path))
            else:
                missing_files.append(test_file)
        
        if missing_files:
            print(f"  ⚠️  Missing test files: {', '.join(missing_files)}")
        
        if not existing_files:
            print(f"  ❌ No test files found for {category_name}")
            return False
        
        # Build pytest command
        cmd = ["python", "-m", "pytest"] + existing_files
        
        # Add standard arguments
        cmd.extend(["-v", "--tb=short"])
        
        if self.args.verbose:
            cmd.append("-s")
        
        if self.args.parallel:
            cmd.extend(["-n", "auto"])
        
        if additional_args:
            cmd.extend(additional_args)
        
        # Run the tests
        try:
            print(f"  🔍 Running {len(existing_files)} test files...")
            
            result = subprocess.run(
                cmd,
                cwd=self.test_dir.parent,
                timeout=timeout,
                capture_output=not self.args.verbose,
                text=True
            )
            
            if result.returncode == 0:
                print(f"  ✅ All {category_name} passed")
                return True
            else:
                print(f"  ❌ {category_name} failed (exit code: {result.returncode})")
                if not self.args.verbose and result.stdout:
                    print("  📄 Test output:")
                    print("    " + "\n    ".join(result.stdout.split("\n")[-10:]))
                return False
                
        except subprocess.TimeoutExpired:
            print(f"  ⏰ {category_name} timed out after {timeout} seconds")
            return False
        except Exception as e:
            print(f"  💥 {category_name} failed with error: {e}")
            return False
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available"""
        required_packages = ["pytest", "fastapi", "sqlalchemy"]
        optional_packages = ["pytest-xdist", "pytest-cov", "pytest-json-report"]
        
        missing_required = []
        missing_optional = []
        
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_required.append(package)
        
        for package in optional_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_optional.append(package)
        
        if missing_required:
            print(f"❌ Missing required packages: {', '.join(missing_required)}")
            print("   Please install them with: pip install " + " ".join(missing_required))
            return False
        
        if missing_optional:
            print(f"⚠️  Missing optional packages: {', '.join(missing_optional)}")
            print("   Install them for enhanced features: pip install " + " ".join(missing_optional))
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run comprehensive test suite for reporting module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_comprehensive_tests.py --all          # Run all tests
  python run_comprehensive_tests.py --quick        # Run essential tests only
  python run_comprehensive_tests.py --performance  # Run performance tests
  python run_comprehensive_tests.py --security     # Run security tests
  python run_comprehensive_tests.py --verbose      # Verbose output
        """
    )
    
    # Test selection options
    parser.add_argument("--all", action="store_true", 
                       help="Run all test categories (default)")
    parser.add_argument("--quick", action="store_true",
                       help="Run only essential tests for quick validation")
    parser.add_argument("--integration", action="store_true",
                       help="Run integration tests")
    parser.add_argument("--performance", action="store_true",
                       help="Run performance benchmark tests")
    parser.add_argument("--security", action="store_true",
                       help="Run security and access control tests")
    
    # Execution options
    parser.add_argument("--verbose", action="store_true",
                       help="Show verbose output including print statements")
    parser.add_argument("--parallel", action="store_true",
                       help="Run tests in parallel (requires pytest-xdist)")
    
    args = parser.parse_args()
    
    # Create and run test runner
    runner = ComprehensiveTestRunner(args)
    
    # Check dependencies first
    if not runner._check_dependencies():
        sys.exit(1)
    
    # Run tests
    success = runner.run()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()