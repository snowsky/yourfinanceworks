#!/bin/bash

# Script to run search reindexing in Docker container

echo "Running search reindexing..."

# Check if running in Docker
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container"
    python /app/scripts/reindex_search_data.py
else
    echo "Running search reindexing via Docker..."
    docker-compose exec api python scripts/reindex_search_data.py
fi

echo "Search reindexing completed!"