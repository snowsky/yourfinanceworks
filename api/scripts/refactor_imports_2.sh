#!/bin/bash

# Specific fix for CloudStorageConfig
find api -name "*.py" -exec sed -i '' 's/from settings.cloud_storage_config/from commercial.cloud_storage.config/g' {} +

# Generic Core Replacements
find api -name "*.py" -exec sed -i '' 's/from settings/from core.settings/g' {} +
find api -name "*.py" -exec sed -i '' 's/from schemas/from core.schemas/g' {} +
find api -name "*.py" -exec sed -i '' 's/from middleware/from core.middleware/g' {} +
find api -name "*.py" -exec sed -i '' 's/from exceptions/from core.exceptions/g' {} +
find api -name "*.py" -exec sed -i '' 's/from constants/from core.constants/g' {} +

# Fix potential double core.core issues
find api -name "*.py" -exec sed -i '' 's/from core.core./from core./g' {} +
