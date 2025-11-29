#!/bin/bash

# 1. Specific Commercial Replacements
# Cloud Storage
find api -name "*.py" -exec sed -i '' 's/from services.cloud_storage_service/from commercial.cloud_storage.service/g' {} +
find api -name "*.py" -exec sed -i '' 's/from services.cloud_storage/from commercial.cloud_storage.providers/g' {} +
find api -name "*.py" -exec sed -i '' 's/from routers.cloud_storage/from commercial.cloud_storage.router/g' {} +

# Tax Integration
find api -name "*.py" -exec sed -i '' 's/from services.tax_integration_service/from commercial.integrations.tax.service/g' {} +
find api -name "*.py" -exec sed -i '' 's/from routers.tax_integration/from commercial.integrations.tax.router/g' {} +

# Slack Integration
find api -name "*.py" -exec sed -i '' 's/from routers.slack_simplified/from commercial.integrations.slack.router/g' {} +

# Email Integration
find api -name "*.py" -exec sed -i '' 's/from services.email_ingestion_service/from commercial.integrations.email.service/g' {} +
find api -name "*.py" -exec sed -i '' 's/from routers.email_integration/from commercial.integrations.email.router/g' {} +

# Approvals
find api -name "*.py" -exec sed -i '' 's/from services.approval_/from commercial.workflows.approvals.services.approval_/g' {} +
find api -name "*.py" -exec sed -i '' 's/from routers.approvals/from commercial.workflows.approvals.router/g' {} +

# Batch Processing
find api -name "*.py" -exec sed -i '' 's/from services.batch_processing_service/from commercial.batch_processing.service/g' {} +
find api -name "*.py" -exec sed -i '' 's/from routers.batch_processing/from commercial.batch_processing.router/g' {} +

# API Access
find api -name "*.py" -exec sed -i '' 's/from routers.external_api_auth/from commercial.api_access.router/g' {} +


# 2. Generic Core Replacements
# Use simple pattern matching
find api -name "*.py" -exec sed -i '' 's/from services/from core.services/g' {} +
find api -name "*.py" -exec sed -i '' 's/from models/from core.models/g' {} +
find api -name "*.py" -exec sed -i '' 's/from routers/from core.routers/g' {} +
find api -name "*.py" -exec sed -i '' 's/from utils/from core.utils/g' {} +

# Fix potential double core.core issues
find api -name "*.py" -exec sed -i '' 's/from core.core./from core./g' {} +
find api -name "*.py" -exec sed -i '' 's/from core.commercial./from commercial./g' {} +
