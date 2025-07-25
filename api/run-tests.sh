#!/bin/bash

echo "🧪 Running API Tests"
echo "==================="

# Install dependencies
pip install -r requirements.txt

# Run tests with explicit path to avoid scripts directory
pytest tests/ -v --cov=tests --cov-report=html --cov-report=term-missing

echo "✅ API tests completed"
echo "📊 Coverage report: htmlcov/index.html"