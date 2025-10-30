#!/bin/bash

# External API Examples using curl
# Replace YOUR_API_KEY and YOUR_DOMAIN with actual values

API_KEY="ak_your_api_key_here"
BASE_URL="https://your-domain.com"

echo "🏦 Bank Statement API - curl Examples"
echo "====================================="

# 1. Health Check
echo -e "\n1️⃣ Health Check"
curl -X GET "${BASE_URL}/api/v1/statements/health" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  | jq '.'

# 2. Get Usage Statistics
echo -e "\n2️⃣ Usage Statistics"
curl -X GET "${BASE_URL}/api/v1/statements/usage" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  | jq '.'

# 3. Process PDF Statement (returns CSV)
echo -e "\n3️⃣ Process PDF Statement (CSV format)"
curl -X POST "${BASE_URL}/api/v1/statements/process" \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "file=@bank_statement.pdf" \
  -F "format=csv" \
  -o "transactions.csv"

echo "CSV saved to transactions.csv"

# 4. Process PDF Statement (returns JSON)
echo -e "\n4️⃣ Process PDF Statement (JSON format)"
curl -X POST "${BASE_URL}/api/v1/statements/process" \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "file=@bank_statement.pdf" \
  -F "format=json" \
  | jq '.'

# 5. Process CSV Statement
echo -e "\n5️⃣ Process CSV Statement"
curl -X POST "${BASE_URL}/api/v1/statements/process" \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "file=@bank_export.csv" \
  -F "format=json" \
  | jq '.'

echo -e "\n✅ Examples completed!"
echo "Note: Replace API_KEY and BASE_URL with your actual values"