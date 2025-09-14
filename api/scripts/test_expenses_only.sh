#!/bin/bash

# Simple Expense Creation Test Script
# This script creates expenses that are visible in the UI

set -e  # Exit on any error

# Configuration
BASE_URL="http://localhost:8000"
UI_URL="http://localhost:8080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_step() {
    echo -e "${BLUE}📋 Step $1: $2${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Test configuration
TEST_EMAIL="apitest@example.com"
TEST_PASSWORD="testpassword123"
JWT_TOKEN=""

echo -e "${BLUE}💰 Expense Creation Test Script${NC}"
echo "=================================================="
echo "This script creates expenses visible in the UI"
echo ""

# Step 1: Health Check
print_step "1" "Health Check"
if curl -s -f "$BASE_URL/health" > /dev/null; then
    print_success "API server is running"
else
    print_error "API server is not accessible at $BASE_URL"
    exit 1
fi

# Step 2: User Login
print_step "2" "User Authentication"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
    print_success "User logged in successfully"
    print_info "JWT Token: ${JWT_TOKEN:0:20}..."
else
    print_error "Login failed. Response: $LOGIN_RESPONSE"
    exit 1
fi

# Step 3: Create Sample Receipt Files
print_step "3" "Create Sample Receipt Files"

# Create temporary directory for sample receipts
TEMP_DIR=$(mktemp -d)
print_info "Creating sample receipt files in: $TEMP_DIR"

# Create sample receipt images (simple PNG files)
# We'll create minimal PNG files using ImageMagick if available, or use a different approach

if command -v convert >/dev/null 2>&1; then
    # Use ImageMagick to create simple receipt images
    print_info "Using ImageMagick to create receipt images..."
    
    convert -size 400x600 xc:white \
        -font "Courier" -pointsize 12 -fill black \
        -annotate +20+30 "ADOBE CREATIVE SUITE" \
        -annotate +20+50 "Invoice #: SUB-2024-001" \
        -annotate +20+70 "Date: $(date +%Y-%m-%d)" \
        -annotate +20+90 "Amount: \$99.99" \
        -annotate +20+110 "Tax: \$8.50" \
        -annotate +20+130 "Total: \$108.49" \
        -annotate +20+150 "Payment: Credit Card ****1234" \
        "$TEMP_DIR/adobe_receipt.png"
    
    convert -size 400x600 xc:white \
        -font "Courier" -pointsize 12 -fill black \
        -annotate +20+30 "DELTA AIRLINES" \
        -annotate +20+50 "Confirmation #: TRV-2024-002" \
        -annotate +20+70 "Flight: DL1234 SFO-LAX" \
        -annotate +20+90 "Date: $(date -v-1d +%Y-%m-%d)" \
        -annotate +20+110 "Amount: \$450.00" \
        -annotate +20+130 "Payment: Corporate Card" \
        "$TEMP_DIR/delta_receipt.png"
    
    convert -size 400x600 xc:white \
        -font "Courier" -pointsize 12 -fill black \
        -annotate +20+30 "STAPLES OFFICE SUPPLIES" \
        -annotate +20+50 "Receipt #: OFF-2024-003" \
        -annotate +20+70 "Date: $(date -v-2d +%Y-%m-%d)" \
        -annotate +20+90 "Paper: \$25.00" \
        -annotate +20+110 "Pens: \$15.75" \
        -annotate +20+130 "Folders: \$12.00" \
        -annotate +20+150 "Ink: \$73.00" \
        -annotate +20+170 "Total: \$136.44" \
        "$TEMP_DIR/staples_receipt.png"
else
    # Fallback: Create simple text files and rename them as .jpg (they'll still work for testing)
    print_info "ImageMagick not available, creating simple text files as .jpg..."
    
    cat > "$TEMP_DIR/adobe_receipt.jpg" << 'EOF'
ADOBE CREATIVE SUITE SUBSCRIPTION
Invoice #: SUB-2024-001
Date: $(date +%Y-%m-%d)
Amount: $99.99
Tax: $8.50
Total: $108.49
Payment Method: Credit Card ****1234
Monthly subscription for design team
EOF

    cat > "$TEMP_DIR/delta_receipt.jpg" << 'EOF'
DELTA AIRLINES
Confirmation #: TRV-2024-002
Flight: DL1234 SFO-LAX
Date: $(date -v-1d +%Y-%m-%d)
Passenger: Business Traveler
Amount: $450.00
Payment: Corporate Card
Business trip to client meeting
EOF

    cat > "$TEMP_DIR/staples_receipt.jpg" << 'EOF'
STAPLES OFFICE SUPPLIES
Receipt #: OFF-2024-003
Date: $(date -v-2d +%Y-%m-%d)
Items:
- Paper (5 reams) - $25.00
- Pens (10 pack) - $15.75
- Folders (20 pack) - $12.00
- Printer Ink - $73.00
Subtotal: $125.75
Tax: $10.69
Total: $136.44
EOF
fi

print_success "Sample receipt files created"

# Step 4: Create Multiple Expenses with Attachments
print_step "4" "Create Multiple Expenses with Attachments"

EXPENSE_IDS=()

# Expense 1: Software subscription (with attachment)
print_info "Creating software expense with receipt..."
EXPENSE_DATA_1='{
    "amount": 99.99,
    "currency": "USD",
    "expense_date": "'$(date +%Y-%m-%d)'",
    "category": "Software",
    "vendor": "Adobe Creative Suite",
    "labels": ["software", "design", "monthly"],
    "tax_rate": 8.5,
    "tax_amount": 8.50,
    "total_amount": 108.49,
    "payment_method": "Credit Card",
    "reference_number": "SUB-2024-001",
    "status": "recorded",
    "notes": "Monthly Adobe Creative Suite subscription for design team",
    "imported_from_attachment": true,
    "analysis_status": "queued"
}'

EXPENSE_RESPONSE_1=$(curl -s -X POST "$BASE_URL/api/v1/expenses/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "$EXPENSE_DATA_1")

if echo "$EXPENSE_RESPONSE_1" | grep -q "id"; then
    EXPENSE_ID_1=$(echo "$EXPENSE_RESPONSE_1" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    EXPENSE_IDS+=("$EXPENSE_ID_1")
    print_success "Software expense created: ID $EXPENSE_ID_1"
    
    # Upload receipt file
    print_info "Uploading receipt for expense $EXPENSE_ID_1..."
    if [ -f "$TEMP_DIR/adobe_receipt.png" ]; then
        RECEIPT_FILE="$TEMP_DIR/adobe_receipt.png"
    else
        RECEIPT_FILE="$TEMP_DIR/adobe_receipt.jpg"
    fi
    UPLOAD_RESPONSE_1=$(curl -s -X POST "$BASE_URL/api/v1/expenses/$EXPENSE_ID_1/upload-receipt" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        -F "file=@$RECEIPT_FILE")
    
    if echo "$UPLOAD_RESPONSE_1" | grep -q "uploaded successfully\|filename"; then
        print_success "Receipt uploaded successfully for expense $EXPENSE_ID_1"
    else
        print_error "Receipt upload failed: $UPLOAD_RESPONSE_1"
    fi
else
    print_error "Software expense failed: $EXPENSE_RESPONSE_1"
fi

# Expense 2: Travel expense (with attachment)
print_info "Creating travel expense with receipt..."
EXPENSE_DATA_2='{
    "amount": 450.00,
    "currency": "USD",
    "expense_date": "'$(date -v-1d +%Y-%m-%d)'",
    "category": "Travel",
    "vendor": "Delta Airlines",
    "labels": ["travel", "flight", "business"],
    "payment_method": "Corporate Card",
    "reference_number": "TRV-2024-002",
    "status": "recorded",
    "notes": "Flight to client meeting in San Francisco",
    "imported_from_attachment": true,
    "analysis_status": "queued"
}'

EXPENSE_RESPONSE_2=$(curl -s -X POST "$BASE_URL/api/v1/expenses/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "$EXPENSE_DATA_2")

if echo "$EXPENSE_RESPONSE_2" | grep -q "id"; then
    EXPENSE_ID_2=$(echo "$EXPENSE_RESPONSE_2" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    EXPENSE_IDS+=("$EXPENSE_ID_2")
    print_success "Travel expense created: ID $EXPENSE_ID_2"
    
    # Upload receipt file
    print_info "Uploading receipt for expense $EXPENSE_ID_2..."
    if [ -f "$TEMP_DIR/delta_receipt.png" ]; then
        RECEIPT_FILE="$TEMP_DIR/delta_receipt.png"
    else
        RECEIPT_FILE="$TEMP_DIR/delta_receipt.jpg"
    fi
    UPLOAD_RESPONSE_2=$(curl -s -X POST "$BASE_URL/api/v1/expenses/$EXPENSE_ID_2/upload-receipt" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        -F "file=@$RECEIPT_FILE")
    
    if echo "$UPLOAD_RESPONSE_2" | grep -q "uploaded successfully\|filename"; then
        print_success "Receipt uploaded successfully for expense $EXPENSE_ID_2"
    else
        print_error "Receipt upload failed: $UPLOAD_RESPONSE_2"
    fi
else
    print_error "Travel expense failed: $EXPENSE_RESPONSE_2"
fi

# Expense 3: Office supplies (with attachment)
print_info "Creating office supplies expense with receipt..."
EXPENSE_DATA_3='{
    "amount": 125.75,
    "currency": "USD",
    "expense_date": "'$(date -v-2d +%Y-%m-%d)'",
    "category": "Office Supplies",
    "vendor": "Staples",
    "labels": ["office", "supplies", "stationery"],
    "payment_method": "Debit Card",
    "reference_number": "OFF-2024-003",
    "status": "recorded",
    "notes": "Monthly office supplies: paper, pens, folders, printer ink",
    "imported_from_attachment": true,
    "analysis_status": "queued"
}'

EXPENSE_RESPONSE_3=$(curl -s -X POST "$BASE_URL/api/v1/expenses/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "$EXPENSE_DATA_3")

if echo "$EXPENSE_RESPONSE_3" | grep -q "id"; then
    EXPENSE_ID_3=$(echo "$EXPENSE_RESPONSE_3" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    EXPENSE_IDS+=("$EXPENSE_ID_3")
    print_success "Office supplies expense created: ID $EXPENSE_ID_3"
    
    # Upload receipt file
    print_info "Uploading receipt for expense $EXPENSE_ID_3..."
    if [ -f "$TEMP_DIR/staples_receipt.png" ]; then
        RECEIPT_FILE="$TEMP_DIR/staples_receipt.png"
    else
        RECEIPT_FILE="$TEMP_DIR/staples_receipt.jpg"
    fi
    UPLOAD_RESPONSE_3=$(curl -s -X POST "$BASE_URL/api/v1/expenses/$EXPENSE_ID_3/upload-receipt" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        -F "file=@$RECEIPT_FILE")
    
    if echo "$UPLOAD_RESPONSE_3" | grep -q "uploaded successfully\|filename"; then
        print_success "Receipt uploaded successfully for expense $EXPENSE_ID_3"
    else
        print_error "Receipt upload failed: $UPLOAD_RESPONSE_3"
    fi
else
    print_error "Office supplies expense failed: $EXPENSE_RESPONSE_3"
fi

# Expense 4: Meals & Entertainment (WITHOUT attachment - to test disabled Process Again button)
print_info "Creating meals expense without receipt..."
EXPENSE_DATA_4='{
    "amount": 85.50,
    "currency": "USD",
    "expense_date": "'$(date -v-3d +%Y-%m-%d)'",
    "category": "Meals & Entertainment",
    "vendor": "The Business Bistro",
    "labels": ["meals", "client", "entertainment"],
    "payment_method": "Credit Card",
    "reference_number": "MEL-2024-004",
    "status": "recorded",
    "notes": "Client dinner meeting - discussing Q1 project requirements"
}'

EXPENSE_RESPONSE_4=$(curl -s -X POST "$BASE_URL/api/v1/expenses/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "$EXPENSE_DATA_4")

if echo "$EXPENSE_RESPONSE_4" | grep -q "id"; then
    EXPENSE_ID_4=$(echo "$EXPENSE_RESPONSE_4" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    EXPENSE_IDS+=("$EXPENSE_ID_4")
    print_success "Meals expense created: ID $EXPENSE_ID_4"
else
    print_error "Meals expense failed: $EXPENSE_RESPONSE_4"
fi

# Expense 5: Marketing expense (WITHOUT attachment - to test disabled Process Again button)
print_info "Creating marketing expense without receipt..."
EXPENSE_DATA_5='{
    "amount": 299.00,
    "currency": "USD",
    "expense_date": "'$(date -v-4d +%Y-%m-%d)'",
    "category": "Marketing",
    "vendor": "Google Ads",
    "labels": ["marketing", "advertising", "digital"],
    "payment_method": "Credit Card",
    "reference_number": "MKT-2024-005",
    "status": "recorded",
    "notes": "Monthly Google Ads campaign for lead generation"
}'

EXPENSE_RESPONSE_5=$(curl -s -X POST "$BASE_URL/api/v1/expenses/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -d "$EXPENSE_DATA_5")

if echo "$EXPENSE_RESPONSE_5" | grep -q "id"; then
    EXPENSE_ID_5=$(echo "$EXPENSE_RESPONSE_5" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    EXPENSE_IDS+=("$EXPENSE_ID_5")
    print_success "Marketing expense created: ID $EXPENSE_ID_5"
else
    print_error "Marketing expense failed: $EXPENSE_RESPONSE_5"
fi

print_info "Created ${#EXPENSE_IDS[@]} expenses total"

# Step 5: List created expenses
print_step "5" "Verify Created Expenses"
EXPENSES_LIST=$(curl -s -X GET "$BASE_URL/api/v1/expenses/" \
    -H "Authorization: Bearer $JWT_TOKEN")

echo "Recent expenses:"
echo "$EXPENSES_LIST" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        # Show last 10 expenses
        recent = data[-10:] if len(data) > 10 else data
        print(f'Showing {len(recent)} most recent expenses (of {len(data)} total):')
        for i, exp in enumerate(reversed(recent)):
            print(f'  {i+1}. {exp.get(\"category\", \"N/A\")} - \${exp.get(\"amount\", \"0\")} {exp.get(\"currency\", \"\")} ({exp.get(\"vendor\", \"N/A\")})')
            print(f'      ID: {exp.get(\"id\", \"N/A\")}, Date: {exp.get(\"expense_date\", \"N/A\")}, Status: {exp.get(\"status\", \"N/A\")}')
    else:
        print(f'Unexpected response format: {type(data)}')
        print(f'Response: {data}')
except Exception as e:
    print(f'Error parsing response: {e}')
    print(f'Raw response: {sys.stdin.read()}')
"

# Step 6: Show summary statistics
print_step "6" "Summary Statistics"

# Get expense totals
EXPENSE_SUMMARY=$(echo "$EXPENSES_LIST" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        total = sum(float(exp.get('amount', 0)) for exp in data)
        count = len(data)
        categories = {}
        for exp in data:
            cat = exp.get('category', 'Unknown')
            categories[cat] = categories.get(cat, 0) + float(exp.get('amount', 0))
        
        print(f'{count} expenses totaling \${total:.2f}')
        print('Top categories:')
        for cat, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f'  - {cat}: \${amount:.2f}')
    else:
        print('0 expenses')
except Exception as e:
    print(f'Error calculating expense summary: {e}')
")

echo "Database summary:"
echo "$EXPENSE_SUMMARY"

# Summary
echo ""
echo "=================================================="
print_success "Expense Creation Complete!"
echo ""
echo "Summary of created content:"
echo "  • API Server: $BASE_URL"
echo "  • Test User: $TEST_EMAIL"
echo "  • Expenses Created: ${#EXPENSE_IDS[@]}"
echo ""

if [ ${#EXPENSE_IDS[@]} -gt 0 ]; then
    echo "Created Expense IDs:"
    for i in "${!EXPENSE_IDS[@]}"; do
        echo "  $((i+1)). ${EXPENSE_IDS[i]}"
    done
    echo ""
fi

print_info "Expenses are now visible in the UI!"
echo ""
echo "View your created expenses:"
echo "  • Expenses Page: $UI_URL/expenses"
echo "  • Dashboard: $UI_URL/dashboard"
echo ""
print_success "All expenses created successfully and ready to view in the UI! 🎉"

# Cleanup temporary files
print_step "7" "Cleanup"
print_info "Cleaning up temporary receipt files..."
rm -rf "$TEMP_DIR"
print_success "Temporary files cleaned up"
