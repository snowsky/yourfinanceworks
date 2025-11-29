#!/bin/bash

# Docker Deployment Script for Licensing System
# This script deploys the licensing system in a Docker environment

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

log_info "=== Docker Licensing System Deployment ==="

# Step 1: Build containers with licensing support
log_info "Building Docker containers..."
cd "$PROJECT_ROOT"

# Ensure public key is included in Docker build
if [ ! -f "api/core/keys/public_key.pem" ]; then
    log_error "Public key not found. Generate with: docker-compose exec api python scripts/generate_license_keys.py"
    exit 1
fi

# Build API container
docker-compose build api

log_info "✓ Containers built"

# Step 2: Run migrations in container
log_info "Running database migrations..."

docker-compose exec -T api alembic upgrade head

if [ $? -eq 0 ]; then
    log_info "✓ Migrations completed"
else
    log_error "Migration failed"
    exit 1
fi

# Step 3: Initialize license system in container
log_info "Initializing license system..."

docker-compose exec -T api python << 'PYTHON_SCRIPT'
from models.database import SessionLocal
from models.models_per_tenant import InstallationInfo
from datetime import datetime, timedelta

db = SessionLocal()
try:
    # Create installation record if not exists
    installation = db.query(InstallationInfo).first()
    if not installation:
        installation = InstallationInfo(
            tenant_id=1,
            installation_id=f"inst_docker_{datetime.now().strftime('%Y%m%d')}",
            trial_start_date=datetime.now(),
            trial_end_date=datetime.now() + timedelta(days=30),
            is_trial=True
        )
        db.add(installation)
        db.commit()
        print("✓ Installation record created")
    else:
        print("✓ Installation record exists")
except Exception as e:
    print(f"Error: {e}")
    exit(1)
finally:
    db.close()
PYTHON_SCRIPT

# Step 4: Restart API service
log_info "Restarting API service..."
docker-compose restart api

# Wait for service to be ready
log_info "Waiting for API to be ready..."
sleep 10

# Step 5: Verify deployment
log_info "Verifying deployment..."

# Check API health
if docker-compose exec -T api curl -f http://localhost:8000/health > /dev/null 2>&1; then
    log_info "✓ API is healthy"
else
    log_warn "API health check failed"
fi

# Test license service
docker-compose exec -T api python -c "
from services.license_service import LicenseService
service = LicenseService()
print('✓ License service initialized')
"

log_info "=== Deployment Complete ==="
log_info "Access the application at: http://localhost:3000"
log_info "API documentation at: http://localhost:8000/docs"
log_info ""
log_info "To test licensing:"
log_info "1. Navigate to Settings → License in the UI"
log_info "2. Check trial status"
log_info "3. Generate a test license:"
log_info "   docker-compose exec api python license_server/generate_license_cli.py --email test@example.com --name Test --features ai_invoice --duration 365"
