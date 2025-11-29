#!/usr/bin/env python3
"""
Disaster Recovery Management Script.

This script provides command-line management of disaster recovery operations
including testing, monitoring, and maintenance tasks.
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add the parent directory to the path so we can import from api
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from core.models.database import get_db
from commercial.cloud_storage.providers.disaster_recovery_service import (
    DisasterRecoveryService,
    ReplicationConfig
)
from commercial.cloud_storage.providers.disaster_recovery_testing import DisasterRecoveryTestSuite
from commercial.cloud_storage.providers.factory import StorageProviderFactory
from commercial.cloud_storage.config import CloudStorageConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DisasterRecoveryManager:
    """
    Command-line manager for disaster recovery operations.
    """
    
    def __init__(self):
        """Initialize the disaster recovery manager."""
        self.db = next(get_db())
        self.config = CloudStorageConfig()
        self.provider_factory = StorageProviderFactory(self.config)
        
        # Initialize disaster recovery service
        dr_config = ReplicationConfig(
            enabled=getattr(self.config, 'disaster_recovery_enabled', False),
            primary_region=getattr(self.config, 'primary_region', 'us-east-1'),
            backup_regions=getattr(self.config, 'backup_regions', []),
            critical_file_patterns=getattr(self.config, 'critical_file_patterns', ['invoices/', 'contracts/']),
            auto_failover_enabled=getattr(self.config, 'auto_failover_enabled', True)
        )
        
        self.dr_service = DisasterRecoveryService(self.db, self.provider_factory, dr_config)
        self.test_suite = DisasterRecoveryTestSuite(self.db, self.dr_service, self.provider_factory)
    
    async def run_comprehensive_test(self, scenarios=None, parallel=False, output_file=None):
        """
        Run comprehensive disaster recovery tests.
        
        Args:
            scenarios: List of scenario names to run
            parallel: Whether to run tests in parallel
            output_file: File to save test results
        """
        logger.info("Starting comprehensive disaster recovery test")
        
        try:
            results = await self.test_suite.run_comprehensive_test(
                scenarios=scenarios,
                parallel_execution=parallel
            )
            
            # Print summary
            self._print_test_summary(results)
            
            # Save results if output file specified
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"Test results saved to {output_file}")
            
            return results
            
        except Exception as e:
            logger.error(f"Comprehensive test failed: {e}")
            return None
    
    async def run_quick_test(self):
        """
        Run a quick disaster recovery health check.
        """
        logger.info("Running quick disaster recovery health check")
        
        try:
            # Run basic tests
            basic_scenarios = ['basic_replication_test', 'corruption_detection_test']
            results = await self.test_suite.run_comprehensive_test(
                scenarios=basic_scenarios,
                parallel_execution=True
            )
            
            self._print_test_summary(results)
            return results
            
        except Exception as e:
            logger.error(f"Quick test failed: {e}")
            return None
    
    async def check_replication_status(self, file_key=None):
        """
        Check replication status for files.
        
        Args:
            file_key: Specific file key to check (optional)
        """
        logger.info("Checking replication status")
        
        try:
            if file_key:
                # Check specific file
                record = self.dr_service.get_replication_status(file_key)
                if record:
                    self._print_replication_record(record)
                else:
                    logger.info(f"No replication record found for {file_key}")
            else:
                # Get overall statistics
                stats = self.dr_service.get_replication_statistics()
                self._print_replication_statistics(stats)
            
        except Exception as e:
            logger.error(f"Failed to check replication status: {e}")
    
    async def test_failover(self, region=None):
        """
        Test automatic failover functionality.
        
        Args:
            region: Region to simulate failure for
        """
        logger.info(f"Testing failover for region: {region or 'primary'}")
        
        try:
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                logger.error("No primary provider available")
                return
            
            failed_region = region or self.dr_service.config.primary_region
            
            success = await self.dr_service.automatic_failover(
                failed_region=failed_region,
                provider_type=primary_provider.provider_type
            )
            
            if success:
                logger.info("Failover test completed successfully")
            else:
                logger.error("Failover test failed")
            
        except Exception as e:
            logger.error(f"Failover test failed: {e}")
    
    async def restore_file(self, file_key, source_region=None):
        """
        Restore a file from backup regions.
        
        Args:
            file_key: File key to restore
            source_region: Preferred source region for restoration
        """
        logger.info(f"Restoring file: {file_key}")
        
        try:
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                logger.error("No primary provider available")
                return
            
            result = await self.dr_service.restore_from_backup(
                file_key=file_key,
                provider=primary_provider,
                preferred_region=source_region
            )
            
            if result.success:
                logger.info(f"File restored successfully: {file_key}")
            else:
                logger.error(f"File restoration failed: {result.error_message}")
            
        except Exception as e:
            logger.error(f"File restoration failed: {e}")
    
    async def run_corruption_check(self, file_key=None):
        """
        Run corruption detection on files.
        
        Args:
            file_key: Specific file to check (optional)
        """
        logger.info("Running corruption detection")
        
        try:
            primary_provider = self.provider_factory.get_primary_provider()
            if not primary_provider:
                logger.error("No primary provider available")
                return
            
            if file_key:
                # Check specific file
                is_corrupted, error_msg = await self.dr_service.detect_corruption(
                    file_key, primary_provider
                )
                
                if is_corrupted:
                    logger.warning(f"Corruption detected in {file_key}: {error_msg}")
                else:
                    logger.info(f"No corruption detected in {file_key}")
            else:
                # Check all replicated files
                stats = self.dr_service.get_replication_statistics()
                logger.info(f"Checking {stats['total_files']} replicated files for corruption")
                
                # This would be implemented to check all files
                logger.info("Bulk corruption check not yet implemented")
            
        except Exception as e:
            logger.error(f"Corruption check failed: {e}")
    
    def show_configuration(self):
        """
        Display current disaster recovery configuration.
        """
        logger.info("Disaster Recovery Configuration:")
        config = self.dr_service.config
        
        print(f"  Enabled: {config.enabled}")
        print(f"  Primary Region: {config.primary_region}")
        print(f"  Backup Regions: {config.backup_regions}")
        print(f"  Auto Failover: {config.auto_failover_enabled}")
        print(f"  Critical File Patterns: {config.critical_file_patterns}")
        print(f"  Max Backup Versions: {config.max_backup_versions}")
        print(f"  Corruption Check Interval: {config.corruption_check_interval_hours} hours")
        print(f"  Recovery Test Interval: {config.recovery_test_interval_days} days")
    
    def _print_test_summary(self, results):
        """
        Print formatted test summary.
        
        Args:
            results: Test results dictionary
        """
        summary = results['test_execution_summary']
        dr_status = results['disaster_recovery_status']
        
        print("\n" + "="*60)
        print("DISASTER RECOVERY TEST SUMMARY")
        print("="*60)
        
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Partial: {summary['partial_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        print(f"Execution Time: {summary['total_execution_time_seconds']} seconds")
        
        print(f"\nOverall Health: {dr_status['overall_health'].upper()}")
        print(f"Replication Functional: {'✓' if dr_status['replication_functional'] else '✗'}")
        print(f"Failover Functional: {'✓' if dr_status['failover_functional'] else '✗'}")
        print(f"Restoration Functional: {'✓' if dr_status['restoration_functional'] else '✗'}")
        
        if results.get('recommendations'):
            print("\nRecommendations:")
            for rec in results['recommendations']:
                print(f"  • {rec}")
        
        print("\nDetailed Results:")
        for test_result in results['test_results']:
            status_symbol = {
                'passed': '✓',
                'failed': '✗',
                'partial': '⚠'
            }.get(test_result['status'], '?')
            
            print(f"  {status_symbol} {test_result['scenario_name']}: {test_result['status']}")
            if test_result.get('error_message'):
                print(f"    Error: {test_result['error_message']}")
        
        print("="*60)
    
    def _print_replication_record(self, record):
        """
        Print formatted replication record.
        
        Args:
            record: Replication record to print
        """
        print(f"\nReplication Record for: {record.file_key}")
        print(f"  Status: {record.status.value}")
        print(f"  Primary Region: {record.primary_region}")
        print(f"  Primary Checksum: {record.primary_checksum}")
        print(f"  Last Replicated: {record.last_replicated}")
        
        if record.backup_regions:
            print("  Backup Regions:")
            for region, checksum in record.backup_regions.items():
                print(f"    {region}: {checksum}")
        
        if record.error_message:
            print(f"  Error: {record.error_message}")
    
    def _print_replication_statistics(self, stats):
        """
        Print formatted replication statistics.
        
        Args:
            stats: Statistics dictionary
        """
        print("\nReplication Statistics:")
        print(f"  Total Files: {stats['total_files']}")
        print(f"  Replicated Files: {stats['replicated_files']}")
        print(f"  Replication Rate: {stats['replication_rate']:.1f}%")
        print(f"  Average Regions per File: {stats['average_regions']:.1f}")
        
        if stats['status_breakdown']:
            print("  Status Breakdown:")
            for status, count in stats['status_breakdown'].items():
                print(f"    {status}: {count}")
        
        if stats['last_test']:
            print(f"  Last Test: {stats['last_test']}")
        
        config = stats.get('config', {})
        print(f"\nConfiguration:")
        print(f"  Enabled: {config.get('enabled', False)}")
        print(f"  Backup Regions: {config.get('backup_regions', [])}")
        print(f"  Auto Failover: {config.get('auto_failover', False)}")


async def main():
    """
    Main entry point for the disaster recovery manager.
    """
    parser = argparse.ArgumentParser(description='Disaster Recovery Management Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test commands
    test_parser = subparsers.add_parser('test', help='Run disaster recovery tests')
    test_subparsers = test_parser.add_subparsers(dest='test_command')
    
    # Comprehensive test
    comprehensive_parser = test_subparsers.add_parser('comprehensive', help='Run comprehensive test suite')
    comprehensive_parser.add_argument('--scenarios', nargs='+', help='Specific scenarios to run')
    comprehensive_parser.add_argument('--parallel', action='store_true', help='Run tests in parallel')
    comprehensive_parser.add_argument('--output', help='Output file for results')
    
    # Quick test
    test_subparsers.add_parser('quick', help='Run quick health check')
    
    # Status commands
    status_parser = subparsers.add_parser('status', help='Check disaster recovery status')
    status_parser.add_argument('--file-key', help='Check specific file replication status')
    
    # Failover test
    failover_parser = subparsers.add_parser('failover', help='Test failover functionality')
    failover_parser.add_argument('--region', help='Region to simulate failure for')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore file from backup')
    restore_parser.add_argument('file_key', help='File key to restore')
    restore_parser.add_argument('--source-region', help='Preferred source region')
    
    # Corruption check
    corruption_parser = subparsers.add_parser('corruption', help='Check for data corruption')
    corruption_parser.add_argument('--file-key', help='Check specific file')
    
    # Configuration
    subparsers.add_parser('config', help='Show disaster recovery configuration')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize manager
    manager = DisasterRecoveryManager()
    
    try:
        if args.command == 'test':
            if args.test_command == 'comprehensive':
                await manager.run_comprehensive_test(
                    scenarios=args.scenarios,
                    parallel=args.parallel,
                    output_file=args.output
                )
            elif args.test_command == 'quick':
                await manager.run_quick_test()
            else:
                test_parser.print_help()
        
        elif args.command == 'status':
            await manager.check_replication_status(file_key=args.file_key)
        
        elif args.command == 'failover':
            await manager.test_failover(region=args.region)
        
        elif args.command == 'restore':
            await manager.restore_file(args.file_key, source_region=args.source_region)
        
        elif args.command == 'corruption':
            await manager.run_corruption_check(file_key=args.file_key)
        
        elif args.command == 'config':
            manager.show_configuration()
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())