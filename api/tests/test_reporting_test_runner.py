"""
Test Runner and Utilities for Comprehensive Reporting Test Suite

This module provides utilities for running the comprehensive reporting test suite,
including test configuration, data setup, and result reporting.

Requirements covered: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import pytest
import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import subprocess
import tempfile

# Add the parent directory to the path so we can import from the API
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ReportingTestRunner:
    """Main test runner for the comprehensive reporting test suite"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default test configuration"""
        return {
            'test_modules': [
                'test_comprehensive_reporting_suite',
                'test_end_to_end_reporting',
                'test_reporting_performance_benchmarks'
            ],
            'performance_tests': {
                'enabled': True,
                'timeout': 300,  # 5 minutes per performance test
                'memory_limit_mb': 2048,  # 2GB memory limit
                'concurrent_workers': 10
            },
            'integration_tests': {
                'enabled': True,
                'timeout': 120,  # 2 minutes per integration test
                'mock_external_services': True
            },
            'security_tests': {
                'enabled': True,
                'test_data_isolation': True,
                'test_access_control': True,
                'test_audit_logging': True
            },
            'output': {
                'format': 'json',
                'file': 'test_results.json',
                'verbose': True,
                'include_performance_metrics': True
            }
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all comprehensive reporting tests"""
        self.start_time = datetime.now()
        
        print("🚀 Starting Comprehensive Reporting Test Suite")
        print(f"⏰ Started at: {self.start_time}")
        print("=" * 60)
        
        try:
            # Run different test categories
            self.results['unit_tests'] = self._run_unit_tests()
            self.results['integration_tests'] = self._run_integration_tests()
            self.results['performance_tests'] = self._run_performance_tests()
            self.results['security_tests'] = self._run_security_tests()
            self.results['end_to_end_tests'] = self._run_end_to_end_tests()
            
            # Generate summary
            self.results['summary'] = self._generate_summary()
            
        except Exception as e:
            self.results['error'] = str(e)
            print(f"❌ Test suite failed with error: {e}")
        
        finally:
            self.end_time = datetime.now()
            self.results['execution_time'] = (self.end_time - self.start_time).total_seconds()
            
            # Save results
            self._save_results()
            
            # Print summary
            self._print_summary()
        
        return self.results
    
    def _run_unit_tests(self) -> Dict[str, Any]:
        """Run unit tests for reporting components"""
        print("\n📋 Running Unit Tests...")
        
        unit_test_files = [
            'test_report_service.py',
            'test_report_data_aggregator.py',
            'test_report_exporter.py',
            'test_report_template_service.py',
            'test_report_scheduler.py',
            'test_report_validation_service.py',
            'test_report_retry_service.py',
            'test_report_error_handling.py'
        ]
        
        results = {}
        
        for test_file in unit_test_files:
            print(f"  🔍 Running {test_file}...")
            
            result = self._run_pytest_file(test_file, timeout=60)
            results[test_file] = result
            
            if result['passed']:
                print(f"    ✅ {result['tests_run']} tests passed")
            else:
                print(f"    ❌ {result['failures']} failures, {result['errors']} errors")
        
        return results
    
    def _run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests"""
        print("\n🔗 Running Integration Tests...")
        
        if not self.config['integration_tests']['enabled']:
            print("  ⏭️  Integration tests disabled")
            return {'enabled': False}
        
        integration_test_files = [
            'test_reporting_integration.py',
            'test_reporting_integration_simple.py',
            'test_report_data_aggregator_integration.py',
            'test_report_template_integration.py',
            'test_report_scheduler_integration.py'
        ]
        
        results = {}
        
        for test_file in integration_test_files:
            print(f"  🔍 Running {test_file}...")
            
            result = self._run_pytest_file(
                test_file, 
                timeout=self.config['integration_tests']['timeout']
            )
            results[test_file] = result
            
            if result['passed']:
                print(f"    ✅ {result['tests_run']} tests passed")
            else:
                print(f"    ❌ {result['failures']} failures")
        
        return results
    
    def _run_performance_tests(self) -> Dict[str, Any]:
        """Run performance and benchmark tests"""
        print("\n⚡ Running Performance Tests...")
        
        if not self.config['performance_tests']['enabled']:
            print("  ⏭️  Performance tests disabled")
            return {'enabled': False}
        
        performance_test_files = [
            'test_report_performance.py',
            'test_reporting_performance_benchmarks.py'
        ]
        
        results = {}
        
        for test_file in performance_test_files:
            print(f"  🔍 Running {test_file}...")
            
            result = self._run_pytest_file(
                test_file,
                timeout=self.config['performance_tests']['timeout'],
                additional_args=['-s']  # Show print statements for performance metrics
            )
            results[test_file] = result
            
            if result['passed']:
                print(f"    ✅ {result['tests_run']} performance tests passed")
                if 'performance_metrics' in result:
                    self._print_performance_metrics(result['performance_metrics'])
            else:
                print(f"    ❌ {result['failures']} performance test failures")
        
        return results
    
    def _run_security_tests(self) -> Dict[str, Any]:
        """Run security and access control tests"""
        print("\n🔒 Running Security Tests...")
        
        if not self.config['security_tests']['enabled']:
            print("  ⏭️  Security tests disabled")
            return {'enabled': False}
        
        security_test_files = [
            'test_report_security.py',
            'test_report_audit_logging.py'
        ]
        
        results = {}
        
        for test_file in security_test_files:
            print(f"  🔍 Running {test_file}...")
            
            result = self._run_pytest_file(test_file, timeout=120)
            results[test_file] = result
            
            if result['passed']:
                print(f"    ✅ {result['tests_run']} security tests passed")
            else:
                print(f"    ❌ {result['failures']} security test failures")
        
        return results
    
    def _run_end_to_end_tests(self) -> Dict[str, Any]:
        """Run end-to-end workflow tests"""
        print("\n🎯 Running End-to-End Tests...")
        
        e2e_test_files = [
            'test_end_to_end_reporting.py',
            'test_comprehensive_reporting_suite.py'
        ]
        
        results = {}
        
        for test_file in e2e_test_files:
            print(f"  🔍 Running {test_file}...")
            
            result = self._run_pytest_file(test_file, timeout=180)
            results[test_file] = result
            
            if result['passed']:
                print(f"    ✅ {result['tests_run']} E2E tests passed")
            else:
                print(f"    ❌ {result['failures']} E2E test failures")
        
        return results
    
    def _run_pytest_file(self, test_file: str, timeout: int = 60, additional_args: List[str] = None) -> Dict[str, Any]:
        """Run a specific pytest file and return results"""
        test_path = Path(__file__).parent / test_file
        
        if not test_path.exists():
            return {
                'passed': False,
                'error': f'Test file {test_file} not found',
                'tests_run': 0,
                'failures': 0,
                'errors': 1
            }
        
        # Build pytest command
        cmd = ['python', '-m', 'pytest', str(test_path), '-v', '--tb=short']
        
        if additional_args:
            cmd.extend(additional_args)
        
        # Add JSON output for parsing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_output_file = f.name
        
        cmd.extend(['--json-report', f'--json-report-file={json_output_file}'])
        
        try:
            # Run the test
            start_time = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path(__file__).parent.parent
            )
            execution_time = time.time() - start_time
            
            # Parse JSON output if available
            test_results = self._parse_pytest_json_output(json_output_file)
            test_results['execution_time'] = execution_time
            test_results['return_code'] = result.returncode
            test_results['stdout'] = result.stdout
            test_results['stderr'] = result.stderr
            
            return test_results
            
        except subprocess.TimeoutExpired:
            return {
                'passed': False,
                'error': f'Test timed out after {timeout} seconds',
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'execution_time': timeout
            }
        except Exception as e:
            return {
                'passed': False,
                'error': str(e),
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'execution_time': 0
            }
        finally:
            # Clean up temporary file
            try:
                os.unlink(json_output_file)
            except:
                pass
    
    def _parse_pytest_json_output(self, json_file: str) -> Dict[str, Any]:
        """Parse pytest JSON output"""
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            summary = data.get('summary', {})
            
            return {
                'passed': summary.get('failed', 0) == 0 and summary.get('error', 0) == 0,
                'tests_run': summary.get('total', 0),
                'failures': summary.get('failed', 0),
                'errors': summary.get('error', 0),
                'skipped': summary.get('skipped', 0),
                'duration': data.get('duration', 0),
                'tests': data.get('tests', [])
            }
        except Exception:
            return {
                'passed': False,
                'tests_run': 0,
                'failures': 0,
                'errors': 1,
                'parse_error': True
            }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test execution summary"""
        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_execution_time = 0
        
        categories_passed = 0
        total_categories = 0
        
        for category, category_results in self.results.items():
            if category in ['summary', 'execution_time', 'error']:
                continue
            
            total_categories += 1
            category_passed = True
            
            if isinstance(category_results, dict) and 'enabled' in category_results:
                if not category_results['enabled']:
                    continue
            
            for test_file, test_result in category_results.items():
                if isinstance(test_result, dict):
                    total_tests += test_result.get('tests_run', 0)
                    total_failures += test_result.get('failures', 0)
                    total_errors += test_result.get('errors', 0)
                    total_execution_time += test_result.get('execution_time', 0)
                    
                    if not test_result.get('passed', False):
                        category_passed = False
            
            if category_passed:
                categories_passed += 1
        
        return {
            'total_tests': total_tests,
            'total_failures': total_failures,
            'total_errors': total_errors,
            'total_execution_time': total_execution_time,
            'categories_passed': categories_passed,
            'total_categories': total_categories,
            'success_rate': (total_tests - total_failures - total_errors) / total_tests if total_tests > 0 else 0,
            'overall_passed': total_failures == 0 and total_errors == 0
        }
    
    def _print_performance_metrics(self, metrics: Dict[str, Any]):
        """Print performance metrics"""
        print("    📊 Performance Metrics:")
        for metric_name, value in metrics.items():
            if isinstance(value, float):
                print(f"      {metric_name}: {value:.2f}")
            else:
                print(f"      {metric_name}: {value}")
    
    def _save_results(self):
        """Save test results to file"""
        if self.config['output']['file']:
            output_file = Path(self.config['output']['file'])
            
            with open(output_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=str)
            
            print(f"\n💾 Results saved to: {output_file}")
    
    def _print_summary(self):
        """Print test execution summary"""
        print("\n" + "=" * 60)
        print("📊 TEST EXECUTION SUMMARY")
        print("=" * 60)
        
        if 'error' in self.results:
            print(f"❌ Test suite failed: {self.results['error']}")
            return
        
        summary = self.results.get('summary', {})
        
        print(f"⏱️  Total execution time: {self.results.get('execution_time', 0):.1f} seconds")
        print(f"🧪 Total tests run: {summary.get('total_tests', 0)}")
        print(f"✅ Tests passed: {summary.get('total_tests', 0) - summary.get('total_failures', 0) - summary.get('total_errors', 0)}")
        print(f"❌ Tests failed: {summary.get('total_failures', 0)}")
        print(f"💥 Test errors: {summary.get('total_errors', 0)}")
        print(f"📈 Success rate: {summary.get('success_rate', 0) * 100:.1f}%")
        
        if summary.get('overall_passed', False):
            print("\n🎉 ALL TESTS PASSED! The reporting module is ready for production.")
        else:
            print("\n⚠️  Some tests failed. Please review the results and fix issues before deployment.")
        
        # Print category breakdown
        print("\n📋 Category Breakdown:")
        for category, results in self.results.items():
            if category in ['summary', 'execution_time', 'error']:
                continue
            
            if isinstance(results, dict) and 'enabled' in results and not results['enabled']:
                print(f"  {category}: ⏭️  Disabled")
                continue
            
            category_tests = sum(r.get('tests_run', 0) for r in results.values() if isinstance(r, dict))
            category_failures = sum(r.get('failures', 0) for r in results.values() if isinstance(r, dict))
            category_errors = sum(r.get('errors', 0) for r in results.values() if isinstance(r, dict))
            
            if category_failures == 0 and category_errors == 0:
                status = "✅"
            else:
                status = "❌"
            
            print(f"  {category}: {status} {category_tests} tests, {category_failures} failures, {category_errors} errors")


def run_comprehensive_tests(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Main entry point for running comprehensive reporting tests"""
    
    # Load configuration if provided
    config = None
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    
    # Create and run test runner
    runner = ReportingTestRunner(config)
    return runner.run_all_tests()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run comprehensive reporting test suite')
    parser.add_argument('--config', help='Path to test configuration file')
    parser.add_argument('--performance-only', action='store_true', help='Run only performance tests')
    parser.add_argument('--security-only', action='store_true', help='Run only security tests')
    parser.add_argument('--integration-only', action='store_true', help='Run only integration tests')
    
    args = parser.parse_args()
    
    # Modify config based on arguments
    config = None
    if args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    if args.performance_only:
        config['integration_tests'] = {'enabled': False}
        config['security_tests'] = {'enabled': False}
    elif args.security_only:
        config['performance_tests'] = {'enabled': False}
        config['integration_tests'] = {'enabled': False}
    elif args.integration_only:
        config['performance_tests'] = {'enabled': False}
        config['security_tests'] = {'enabled': False}
    
    # Run tests
    runner = ReportingTestRunner(config)
    results = runner.run_all_tests()
    
    # Exit with appropriate code
    summary = results.get('summary', {})
    if summary.get('overall_passed', False):
        sys.exit(0)
    else:
        sys.exit(1)