#!/bin/bash

# Deploy Reporting Module Migration Script
# This script applies the reporting tables migration to both master and tenant databases

set -e

echo "🚀 Starting Reporting Module Migration Deployment..."

# Check if required environment variables are set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable is not set"
    exit 1
fi

# Function to run migration for a specific database type
run_migration() {
    local db_type=$1
    echo "📊 Running migration for $db_type database..."
    
    export ALEMBIC_DB_TYPE=$db_type
    
    # Run the migration
    if alembic upgrade add_reporting_tables; then
        echo "✅ Successfully applied reporting migration to $db_type database"
    else
        echo "❌ Failed to apply reporting migration to $db_type database"
        return 1
    fi
}

# Apply migration to master database (for tenant management)
echo "🏢 Applying migration to master database..."
run_migration "master"

# Apply migration to all tenant databases
echo "🏬 Applying migration to tenant databases..."

# Get list of tenant databases from master database
TENANT_DBS=$(psql "$DATABASE_URL" -t -c "SELECT 'tenant_' || id FROM tenants WHERE is_active = true;" 2>/dev/null | tr -d ' ' | grep -v '^$' || echo "")

if [ -z "$TENANT_DBS" ]; then
    echo "⚠️  No active tenant databases found. Migration will be applied when tenants are created."
else
    echo "📋 Found tenant databases: $(echo $TENANT_DBS | tr '\n' ' ')"
    
    for tenant_db in $TENANT_DBS; do
        echo "🏪 Migrating tenant database: $tenant_db"
        
        # Extract tenant ID from database name
        TENANT_ID=$(echo $tenant_db | sed 's/tenant_//')
        export TENANT_ID=$TENANT_ID
        
        # Run migration for this tenant
        if run_migration "tenant"; then
            echo "✅ Successfully migrated $tenant_db"
        else
            echo "❌ Failed to migrate $tenant_db"
            # Continue with other tenants even if one fails
        fi
    done
fi

echo "🎉 Reporting Module Migration Deployment Complete!"
echo ""
echo "📝 Next Steps:"
echo "   1. Restart the API service to ensure all changes are loaded"
echo "   2. Verify the reporting functionality in the UI"
echo "   3. Check that all reporting endpoints are accessible"
echo ""
echo "🔍 To verify the migration was successful, you can check:"
echo "   - Master database: report_templates, scheduled_reports, report_history tables"
echo "   - Tenant databases: report_templates, scheduled_reports, report_history tables"