#!/bin/bash

# Check cloud storage configuration in both API and OCR worker containers

echo "🔍 Checking Cloud Storage Configuration in Containers"
echo "=================================================="

# Function to run the check script in a container
run_check_in_container() {
    local container_name=$1
    local service_name=$2
    
    echo ""
    echo "📡 Checking $service_name Container ($container_name)"
    echo "----------------------------------------"
    
    # Check if container is running
    if ! docker ps --format "table {{.Names}}" | grep -q "^${container_name}$"; then
        echo "❌ Container $container_name is not running"
        echo "   Try: docker-compose up -d $service_name"
        return 1
    fi
    
    # Run the check script in the container
    docker exec $container_name python /app/scripts/check_cloud_storage_containers.py
    
    return $?
}

# Check API container
echo "🚀 Starting Cloud Storage Configuration Check..."

# Try to find the API container
API_CONTAINER=$(docker ps --format "table {{.Names}}" | grep -E "(api|web)" | head -1)
if [ -z "$API_CONTAINER" ]; then
    echo "❌ Could not find API container. Looking for containers with 'api' or 'web' in name..."
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
    API_CONTAINER="api"  # fallback
fi

# Try to find the OCR worker container
WORKER_CONTAINER=$(docker ps --format "table {{.Names}}" | grep -E "(worker|ocr)" | head -1)
if [ -z "$WORKER_CONTAINER" ]; then
    echo "❌ Could not find OCR worker container. Looking for containers with 'worker' or 'ocr' in name..."
    docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
    WORKER_CONTAINER="ocr-worker"  # fallback
fi

echo "Found containers:"
echo "  API: $API_CONTAINER"
echo "  Worker: $WORKER_CONTAINER"

# Run checks
run_check_in_container "$API_CONTAINER" "API"
api_result=$?

echo ""
echo "=================================================="

run_check_in_container "$WORKER_CONTAINER" "OCR Worker"
worker_result=$?

echo ""
echo "=================================================="
echo "📋 SUMMARY"
echo "=================================================="

if [ $api_result -eq 0 ] && [ $worker_result -eq 0 ]; then
    echo "✅ Both containers checked successfully"
elif [ $api_result -eq 0 ]; then
    echo "⚠️ API container checked successfully, worker container had issues"
elif [ $worker_result -eq 0 ]; then
    echo "⚠️ Worker container checked successfully, API container had issues"
else
    echo "❌ Both containers had issues"
fi

echo ""
echo "💡 Next Steps:"
echo "1. Review the configuration issues identified above"
echo "2. Update environment variables in docker-compose.yml or .env files"
echo "3. Restart containers: docker-compose restart"
echo "4. Test bank statement upload again"

echo ""
echo "🔧 Quick Fix Commands:"
echo "# Enable S3 storage:"
echo "export AWS_S3_ENABLED=true"
echo "export CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3"
echo "export AWS_S3_BUCKET_NAME=your-bucket-name"
echo "export AWS_S3_ACCESS_KEY_ID=your-access-key"
echo "export AWS_S3_SECRET_ACCESS_KEY=your-secret-key"
echo ""
echo "# Then restart containers:"
echo "docker-compose restart"