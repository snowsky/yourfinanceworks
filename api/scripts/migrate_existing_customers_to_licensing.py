#!/usr/bin/env python3
"""
Migration Script for Existing Customers to Licensing System

This script:
1. Creates installation records for all existing tenants
2. Generates licenses with all features enabled
3. Sends notification emails to customers
4. Provides a grace period before enforcement

Usage:
    python migrate_existing_customers_to_licensing.py [options]

Options:
    --dry-run           Show what would be done without making changes
    --grace-days N      Set grace period in days (default: 90)
    --license-years N   Set license duration in years (default: 1)
    --send-emails       Send notification emails to customers
    --skip-inactive     Skip inactive tenants
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.models.database import SessionLocal, get_tenant_db
from core.models.models import Tenant
from core.models.models_per_tenant import InstallationInfo
from core.services.license_service import LicenseService

# Import license generator if available
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../license_server'))
    from license_generator import LicenseGenerator
    from email_service import send_license_email
    LICENSE_GENERATION_AVAILABLE = True
except ImportError:
    LICENSE_GENERATION_AVAILABLE = False
    print("Warning: License generation not available. Install license_server dependencies.")


class CustomerMigration:
    """Handles migration of existing customers to licensing system"""
    
    def __init__(self, dry_run: bool = False, grace_days: int = 90, 
                 license_years: int = 1, send_emails: bool = False,
                 skip_inactive: bool = True):
        self.dry_run = dry_run
        self.grace_days = grace_days
        self.license_years = license_years
        self.send_emails = send_emails
        self.skip_inactive = skip_inactive
        self.db = SessionLocal()
        self.license_service = LicenseService()
        
        if LICENSE_GENERATION_AVAILABLE:
            self.license_generator = LicenseGenerator()
        else:
            self.license_generator = None
    
    def get_all_features(self) -> List[str]:
        """Get list of all available features"""
        return [
            'ai_invoice',
            'ai_expense',
            'ai_bank_statement',
            'ai_chat',
            'tax_integration',
            'slack_integration',
            'cloud_storage',
            'sso_auth',
            'approvals',
            'reporting',
            'batch_processing',
            'inventory',
            'advanced_search'
        ]
    
    def get_existing_tenants(self) -> List[Tenant]:
        """Get all existing tenants"""
        query = self.db.query(Tenant)
        
        if self.skip_inactive:
            query = query.filter(Tenant.is_active == True)
        
        tenants = query.all()
        print(f"Found {len(tenants)} tenants to migrate")
        return tenants
    
    def create_installation_record(self, tenant: Tenant) -> Optional[InstallationInfo]:
        """Create installation record for tenant"""
        try:
            # Check if installation record already exists
            existing = self.db.query(InstallationInfo).filter(
                InstallationInfo.tenant_id == tenant.id
            ).first()
            
            if existing:
                print(f"  ⚠️  Installation record already exists for tenant {tenant.id}")
                return existing
            
            # Create new installation record
            installation = InstallationInfo(
                tenant_id=tenant.id,
                installation_id=f"inst_{tenant.id}_{datetime.now().strftime('%Y%m%d')}",
                trial_start_date=datetime.now(),
                trial_end_date=datetime.now() + timedelta(days=self.grace_days),
                is_trial=False,  # Not a trial, this is a migration
                created_at=datetime.now()
            )
            
            if not self.dry_run:
                self.db.add(installation)
                self.db.commit()
                print(f"  ✅ Created installation record for tenant {tenant.id}")
            else:
                print(f"  [DRY RUN] Would create installation record for tenant {tenant.id}")
            
            return installation
            
        except Exception as e:
            print(f"  ❌ Error creating installation record for tenant {tenant.id}: {e}")
            self.db.rollback()
            return None
    
    def generate_license(self, tenant: Tenant) -> Optional[str]:
        """Generate license key for tenant with all features"""
        if not self.license_generator:
            print(f"  ⚠️  License generation not available for tenant {tenant.id}")
            return None
        
        try:
            # Get tenant email (use admin user email or tenant contact)
            tenant_email = self.get_tenant_email(tenant)
            tenant_name = tenant.name or f"Tenant {tenant.id}"
            
            # Generate license with all features
            features = self.get_all_features()
            duration_days = self.license_years * 365
            
            license_key = self.license_generator.generate_license(
                email=tenant_email,
                customer_name=tenant_name,
                features=features,
                duration_days=duration_days
            )
            
            if not self.dry_run:
                print(f"  ✅ Generated license for tenant {tenant.id}")
            else:
                print(f"  [DRY RUN] Would generate license for tenant {tenant.id}")
            
            return license_key
            
        except Exception as e:
            print(f"  ❌ Error generating license for tenant {tenant.id}: {e}")
            return None
    
    def get_tenant_email(self, tenant: Tenant) -> str:
        """Get email address for tenant"""
        # Try to get admin user email from tenant
        try:
            from core.models.models import User
            admin_user = self.db.query(User).filter(
                User.tenant_id == tenant.id,
                User.role == 'admin'
            ).first()
            
            if admin_user and admin_user.email:
                return admin_user.email
        except Exception:
            pass
        
        # Fallback to generic email
        return f"admin@tenant{tenant.id}.example.com"
    
    def activate_license(self, tenant: Tenant, license_key: str) -> bool:
        """Activate license for tenant"""
        try:
            if not self.dry_run:
                result = self.license_service.activate_license(
                    license_key=license_key,
                    tenant_id=tenant.id
                )
                
                if result.get('success'):
                    print(f"  ✅ Activated license for tenant {tenant.id}")
                    return True
                else:
                    print(f"  ❌ Failed to activate license for tenant {tenant.id}: {result.get('error')}")
                    return False
            else:
                print(f"  [DRY RUN] Would activate license for tenant {tenant.id}")
                return True
                
        except Exception as e:
            print(f"  ❌ Error activating license for tenant {tenant.id}: {e}")
            return False
    
    def send_notification_email(self, tenant: Tenant, license_key: str) -> bool:
        """Send notification email to tenant about new licensing system"""
        if not self.send_emails:
            return True
        
        if not LICENSE_GENERATION_AVAILABLE:
            print(f"  ⚠️  Email service not available for tenant {tenant.id}")
            return False
        
        try:
            tenant_email = self.get_tenant_email(tenant)
            tenant_name = tenant.name or f"Tenant {tenant.id}"
            features = self.get_all_features()
            expires_at = (datetime.now() + timedelta(days=self.license_years * 365)).strftime('%Y-%m-%d')
            
            # Custom email template for migration
            email_body = f"""
Dear {tenant_name},

We're excited to announce that we've upgraded our Invoice Management System with a new licensing system!

As a valued existing customer, we've automatically activated a license for you with ALL features enabled for {self.license_years} year(s).

Your License Details:
- Customer: {tenant_name}
- Email: {tenant_email}
- Features: All features enabled (AI, Integrations, Advanced features)
- Expires: {expires_at}
- Grace Period: {self.grace_days} days

Your License Key:
{license_key}

What This Means for You:
✅ No action required - your license is already activated
✅ All features you currently use remain available
✅ {self.grace_days}-day grace period before enforcement
✅ You can view your license status in Settings → License

What's New:
- Feature-based licensing for granular control
- Trial period for new features
- Easy license management in the UI
- Transparent feature availability

Need Help?
- View license status: Settings → License
- Documentation: https://docs.yourdomain.com/licensing
- Support: support@yourdomain.com

Thank you for being a valued customer!

Best regards,
The Invoice Management Team
"""
            
            if not self.dry_run:
                send_license_email(
                    to_email=tenant_email,
                    customer_name=tenant_name,
                    license_key=license_key,
                    features=features,
                    expires_at=expires_at,
                    custom_message=email_body
                )
                print(f"  ✅ Sent notification email to {tenant_email}")
                return True
            else:
                print(f"  [DRY RUN] Would send email to {tenant_email}")
                return True
                
        except Exception as e:
            print(f"  ❌ Error sending email for tenant {tenant.id}: {e}")
            return False
    
    def migrate_tenant(self, tenant: Tenant) -> Dict:
        """Migrate a single tenant to licensing system"""
        print(f"\n📦 Migrating Tenant {tenant.id}: {tenant.name}")
        
        result = {
            'tenant_id': tenant.id,
            'tenant_name': tenant.name,
            'installation_created': False,
            'license_generated': False,
            'license_activated': False,
            'email_sent': False,
            'errors': []
        }
        
        # Step 1: Create installation record
        installation = self.create_installation_record(tenant)
        if installation:
            result['installation_created'] = True
        else:
            result['errors'].append('Failed to create installation record')
            return result
        
        # Step 2: Generate license
        license_key = self.generate_license(tenant)
        if license_key:
            result['license_generated'] = True
            result['license_key'] = license_key
        else:
            result['errors'].append('Failed to generate license')
            # Continue anyway - they have grace period
        
        # Step 3: Activate license
        if license_key:
            if self.activate_license(tenant, license_key):
                result['license_activated'] = True
            else:
                result['errors'].append('Failed to activate license')
        
        # Step 4: Send notification email
        if license_key and self.send_emails:
            if self.send_notification_email(tenant, license_key):
                result['email_sent'] = True
            else:
                result['errors'].append('Failed to send email')
        
        return result
    
    def run_migration(self) -> Dict:
        """Run migration for all tenants"""
        print("=" * 80)
        print("EXISTING CUSTOMER MIGRATION TO LICENSING SYSTEM")
        print("=" * 80)
        print(f"Dry Run: {self.dry_run}")
        print(f"Grace Period: {self.grace_days} days")
        print(f"License Duration: {self.license_years} year(s)")
        print(f"Send Emails: {self.send_emails}")
        print(f"Skip Inactive: {self.skip_inactive}")
        print("=" * 80)
        
        if self.dry_run:
            print("\n⚠️  DRY RUN MODE - No changes will be made\n")
        
        # Get all tenants
        tenants = self.get_existing_tenants()
        
        if not tenants:
            print("No tenants found to migrate")
            return {'success': True, 'tenants_migrated': 0}
        
        # Migrate each tenant
        results = []
        for tenant in tenants:
            result = self.migrate_tenant(tenant)
            results.append(result)
        
        # Summary
        print("\n" + "=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        
        total = len(results)
        successful = len([r for r in results if not r['errors']])
        installations_created = len([r for r in results if r['installation_created']])
        licenses_generated = len([r for r in results if r['license_generated']])
        licenses_activated = len([r for r in results if r['license_activated']])
        emails_sent = len([r for r in results if r['email_sent']])
        
        print(f"Total Tenants: {total}")
        print(f"Successful: {successful}")
        print(f"Installations Created: {installations_created}")
        print(f"Licenses Generated: {licenses_generated}")
        print(f"Licenses Activated: {licenses_activated}")
        print(f"Emails Sent: {emails_sent}")
        
        # Show errors
        errors = [r for r in results if r['errors']]
        if errors:
            print(f"\n⚠️  {len(errors)} tenants had errors:")
            for result in errors:
                print(f"  Tenant {result['tenant_id']}: {', '.join(result['errors'])}")
        
        print("=" * 80)
        
        if self.dry_run:
            print("\n⚠️  This was a DRY RUN - no changes were made")
            print("Run without --dry-run to apply changes")
        else:
            print("\n✅ Migration complete!")
            print(f"Grace period: {self.grace_days} days")
            print("Customers have been notified via email" if self.send_emails else "No emails sent (use --send-emails)")
        
        return {
            'success': True,
            'total': total,
            'successful': successful,
            'installations_created': installations_created,
            'licenses_generated': licenses_generated,
            'licenses_activated': licenses_activated,
            'emails_sent': emails_sent,
            'results': results
        }
    
    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'db'):
            self.db.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Migrate existing customers to licensing system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would happen
  python migrate_existing_customers_to_licensing.py --dry-run
  
  # Migrate with 90-day grace period
  python migrate_existing_customers_to_licensing.py --grace-days 90
  
  # Migrate and send emails
  python migrate_existing_customers_to_licensing.py --send-emails
  
  # Full migration with 2-year licenses
  python migrate_existing_customers_to_licensing.py --license-years 2 --send-emails
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--grace-days',
        type=int,
        default=90,
        help='Grace period in days before enforcement (default: 90)'
    )
    
    parser.add_argument(
        '--license-years',
        type=int,
        default=1,
        help='License duration in years (default: 1)'
    )
    
    parser.add_argument(
        '--send-emails',
        action='store_true',
        help='Send notification emails to customers'
    )
    
    parser.add_argument(
        '--skip-inactive',
        action='store_true',
        default=True,
        help='Skip inactive tenants (default: True)'
    )
    
    parser.add_argument(
        '--include-inactive',
        action='store_true',
        help='Include inactive tenants'
    )
    
    args = parser.parse_args()
    
    # Override skip_inactive if include-inactive is set
    if args.include_inactive:
        args.skip_inactive = False
    
    # Confirm if not dry run
    if not args.dry_run:
        print("⚠️  WARNING: This will modify the database and potentially send emails")
        print(f"Grace period: {args.grace_days} days")
        print(f"License duration: {args.license_years} year(s)")
        print(f"Send emails: {args.send_emails}")
        response = input("\nContinue? (yes/no): ")
        
        if response.lower() != 'yes':
            print("Migration cancelled")
            return 1
    
    # Run migration
    migration = CustomerMigration(
        dry_run=args.dry_run,
        grace_days=args.grace_days,
        license_years=args.license_years,
        send_emails=args.send_emails,
        skip_inactive=args.skip_inactive
    )
    
    try:
        result = migration.run_migration()
        return 0 if result['success'] else 1
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
