# User Attribution Tracking API Documentation

## Overview

The User Attribution Tracking API provides automatic tracking of user actions across invoices, expenses, bank statements, reminders, and approval workflows. This feature enables organizations to maintain accountability, audit trails, and collaboration visibility by recording who created each record and who performed approval/rejection actions.

## Base URL

```
/api/v1
```

## Authentication

All endpoints require authentication using a Bearer token in the Authorization header:

```
Authorization: Bearer <access_token>
```

User attribution is automatically captured from the authenticated session and cannot be manually overridden.

## Attribution Fields

### Creator Attribution

All entities (invoices, expenses, bank statements, reminders) include the following attribution fields:

```json
{
  "created_by_user_id": 123,
  "created_by_username": "john.doe",
  "created_by_email": "john.doe@example.com"
}
```

**Field Descriptions:**
- `created_by_user_id`: ID of the user who created the record
- `created_by_username`: Username of the creator
- `created_by_email`: Email address of the creator

**Legacy Data Handling:**
- Records created before attribution tracking was implemented will have `null` values
- The API returns `"Unknown"` as the display name for legacy records
- No errors occur when querying records with missing attribution

### Approval Attribution

Approval records include both approver and rejector attribution:

```json
{
  "approved_by_user_id": 456,
  "approved_by_username": "manager.smith",
  "approved_at": "2025-12-06T14:30:00Z",
  "rejected_by_user_id": null,
  "rejected_by_username": null,
  "rejected_at": null
}
```

**Field Descriptions:**
- `approved_by_user_id`: ID of the user who approved the record
- `approved_by_username`: Username of the approver
- `approved_at`: Timestamp when approval occurred
- `rejected_by_user_id`: ID of the user who rejected the record
- `rejected_by_username`: Username of the rejector
- `rejected_at`: Timestamp when rejection occurred

**Mutual Exclusivity:**
- A record can be either approved OR rejected, never both
- Only one set of fields will be populated at a time

## Endpoints

### 1. Invoice Attribution

#### Get Invoice with Attribution

**Endpoint:** `GET /invoices/{invoice_id}`

**Response:**
```json
{
  "id": 123,
  "number": "INV-001",
  "amount": 1000.00,
  "currency": "USD",
  "status": "draft",
  "created_at": "2025-12-01T10:00:00Z",
  "created_by_user_id": 5,
  "created_by_username": "john.doe",
  "created_by_email": "john.doe@example.com",
  "client": {
    "id": 789,
    "name": "Acme Corp"
  }
}
```

#### List Invoices with Attribution

**Endpoint:** `GET /invoices`

**Query Parameters:**
- `created_by_user_id` (optional): Filter by creator user ID
- `skip` (optional): Pagination offset
- `limit` (optional): Pagination limit

**Example Request:**
```bash
GET /invoices?created_by_user_id=5&limit=20
```

**Response:**
```json
{
  "invoices": [
    {
      "id": 123,
      "number": "INV-001",
      "amount": 1000.00,
      "created_at": "2025-12-01T10:00:00Z",
      "created_by_user_id": 5,
      "created_by_username": "john.doe",
      "created_by_email": "john.doe@example.com"
    }
  ],
  "total": 1
}
```

#### Create Invoice (Attribution Automatic)

**Endpoint:** `POST /invoices`

**Request Body:**
```json
{
  "number": "INV-002",
  "amount": 1500.00,
  "currency": "USD",
  "client_id": 789
}
```

**Response:**
```json
{
  "id": 124,
  "number": "INV-002",
  "amount": 1500.00,
  "created_at": "2025-12-06T15:00:00Z",
  "created_by_user_id": 5,
  "created_by_username": "john.doe",
  "created_by_email": "john.doe@example.com"
}
```

**Note:** The `created_by_user_id` is automatically set from the authenticated user and cannot be manually specified.

### 2. Expense Attribution

#### Get Expense with Attribution

**Endpoint:** `GET /expenses/{expense_id}`

**Response:**
```json
{
  "id": 456,
  "amount": 250.00,
  "currency": "USD",
  "category": "Travel",
  "description": "Client meeting transportation",
  "date": "2025-12-05",
  "status": "pending",
  "created_at": "2025-12-05T16:30:00Z",
  "created_by_user_id": 7,
  "created_by_username": "jane.employee",
  "created_by_email": "jane.employee@example.com"
}
```

#### List Expenses with Attribution

**Endpoint:** `GET /expenses`

**Query Parameters:**
- `created_by_user_id` (optional): Filter by creator user ID
- `status` (optional): Filter by expense status
- `skip` (optional): Pagination offset
- `limit` (optional): Pagination limit

**Example Request:**
```bash
GET /expenses?created_by_user_id=7&status=pending
```

**Response:**
```json
{
  "expenses": [
    {
      "id": 456,
      "amount": 250.00,
      "category": "Travel",
      "created_at": "2025-12-05T16:30:00Z",
      "created_by_user_id": 7,
      "created_by_username": "jane.employee",
      "created_by_email": "jane.employee@example.com"
    }
  ],
  "total": 1
}
```

#### Create Expense (Attribution Automatic)

**Endpoint:** `POST /expenses`

**Request Body:**
```json
{
  "amount": 75.50,
  "currency": "USD",
  "category": "Meals",
  "description": "Team lunch",
  "date": "2025-12-06"
}
```

**Response:**
```json
{
  "id": 457,
  "amount": 75.50,
  "category": "Meals",
  "created_at": "2025-12-06T12:00:00Z",
  "created_by_user_id": 7,
  "created_by_username": "jane.employee",
  "created_by_email": "jane.employee@example.com"
}
```

### 3. Bank Statement Attribution

#### Get Bank Statement with Attribution

**Endpoint:** `GET /statements/{statement_id}`

**Response:**
```json
{
  "id": 789,
  "account_name": "Business Checking",
  "statement_date": "2025-11-30",
  "balance": 15000.00,
  "created_at": "2025-12-01T09:00:00Z",
  "created_by_user_id": 3,
  "created_by_username": "accountant.jones",
  "created_by_email": "accountant.jones@example.com"
}
```

#### List Bank Statements with Attribution

**Endpoint:** `GET /statements`

**Query Parameters:**
- `created_by_user_id` (optional): Filter by creator user ID
- `skip` (optional): Pagination offset
- `limit` (optional): Pagination limit

**Example Request:**
```bash
GET /statements?created_by_user_id=3
```

**Response:**
```json
{
  "statements": [
    {
      "id": 789,
      "account_name": "Business Checking",
      "statement_date": "2025-11-30",
      "created_at": "2025-12-01T09:00:00Z",
      "created_by_user_id": 3,
      "created_by_username": "accountant.jones",
      "created_by_email": "accountant.jones@example.com"
    }
  ],
  "total": 1
}
```

### 4. Reminder Attribution

#### Get Reminder with Attribution

**Endpoint:** `GET /reminders/{reminder_id}`

**Response:**
```json
{
  "id": 321,
  "title": "Invoice Payment Due",
  "description": "Follow up on INV-001 payment",
  "due_date": "2025-12-10",
  "created_at": "2025-12-06T10:00:00Z",
  "created_by_user_id": 5,
  "created_by_username": "john.doe",
  "created_by_email": "john.doe@example.com"
}
```

#### List Reminders with Attribution

**Endpoint:** `GET /reminders`

**Query Parameters:**
- `created_by_user_id` (optional): Filter by creator user ID
- `skip` (optional): Pagination offset
- `limit` (optional): Pagination limit

**Example Request:**
```bash
GET /reminders?created_by_user_id=5
```

**Response:**
```json
{
  "reminders": [
    {
      "id": 321,
      "title": "Invoice Payment Due",
      "due_date": "2025-12-10",
      "created_at": "2025-12-06T10:00:00Z",
      "created_by_user_id": 5,
      "created_by_username": "john.doe",
      "created_by_email": "john.doe@example.com"
    }
  ],
  "total": 1
}
```

### 5. Approval Attribution

#### Approve Expense (Attribution Automatic)

**Endpoint:** `POST /approvals/{approval_id}/approve`

**Request Body:**
```json
{
  "notes": "Approved - complies with policy"
}
```

**Response:**
```json
{
  "id": 123,
  "expense_id": 456,
  "status": "approved",
  "approved_at": "2025-12-06T14:30:00Z",
  "approved_by_user_id": 10,
  "approved_by_username": "manager.smith",
  "notes": "Approved - complies with policy"
}
```

**Note:** The `approved_by_user_id` is automatically set from the authenticated user.

#### Reject Expense (Attribution Automatic)

**Endpoint:** `POST /approvals/{approval_id}/reject`

**Request Body:**
```json
{
  "reason": "Missing receipt",
  "notes": "Please upload receipt and resubmit"
}
```

**Response:**
```json
{
  "id": 123,
  "expense_id": 456,
  "status": "rejected",
  "rejected_at": "2025-12-06T14:30:00Z",
  "rejected_by_user_id": 10,
  "rejected_by_username": "manager.smith",
  "reason": "Missing receipt",
  "notes": "Please upload receipt and resubmit"
}
```

#### Get Expense with Approval Attribution

**Endpoint:** `GET /expenses/{expense_id}`

**Response (Approved Expense):**
```json
{
  "id": 456,
  "amount": 250.00,
  "category": "Travel",
  "status": "approved",
  "created_at": "2025-12-05T16:30:00Z",
  "created_by_user_id": 7,
  "created_by_username": "jane.employee",
  "created_by_email": "jane.employee@example.com",
  "approval": {
    "id": 123,
    "status": "approved",
    "approved_at": "2025-12-06T14:30:00Z",
    "approved_by_user_id": 10,
    "approved_by_username": "manager.smith"
  }
}
```

**Response (Rejected Expense):**
```json
{
  "id": 457,
  "amount": 500.00,
  "category": "Equipment",
  "status": "rejected",
  "created_at": "2025-12-05T10:00:00Z",
  "created_by_user_id": 8,
  "created_by_username": "employee.brown",
  "created_by_email": "employee.brown@example.com",
  "approval": {
    "id": 124,
    "status": "rejected",
    "rejected_at": "2025-12-06T11:00:00Z",
    "rejected_by_user_id": 10,
    "rejected_by_username": "manager.smith",
    "reason": "Exceeds budget"
  }
}
```

## Filtering by Creator

All list endpoints support filtering by creator user ID to show records created by a specific user.

### Examples

**Get all invoices created by user 5:**
```bash
GET /invoices?created_by_user_id=5
```

**Get all expenses created by user 7:**
```bash
GET /expenses?created_by_user_id=7
```

**Get all statements created by user 3:**
```bash
GET /statements?created_by_user_id=3
```

**Get all reminders created by user 5:**
```bash
GET /reminders?created_by_user_id=5
```

**Combine with other filters:**
```bash
GET /expenses?created_by_user_id=7&status=pending&category=Travel
```

## Legacy Data Handling

### Records Without Attribution

Records created before the attribution tracking feature was implemented will have `null` values for attribution fields:

```json
{
  "id": 100,
  "number": "INV-OLD-001",
  "amount": 500.00,
  "created_at": "2024-01-15T10:00:00Z",
  "created_by_user_id": null,
  "created_by_username": null,
  "created_by_email": null
}
```

### Display Handling

When displaying records with missing attribution in the UI:

- **Creator Name:** Display as `"Unknown"` or `"System"`
- **Filtering:** Records with `null` creator can be filtered by omitting the `created_by_user_id` parameter
- **No Errors:** The API handles `null` values gracefully without errors

### Example Response with Unknown Creator

```json
{
  "id": 100,
  "number": "INV-OLD-001",
  "amount": 500.00,
  "created_at": "2024-01-15T10:00:00Z",
  "created_by_user_id": null,
  "created_by_username": "Unknown",
  "created_by_email": null
}
```

## Security

### Automatic Attribution

- User attribution is **automatically captured** from the authenticated session
- The `created_by_user_id` field **cannot be manually specified** in create requests
- Approval attribution (`approved_by_user_id`, `rejected_by_user_id`) is **automatically set** during approval/rejection actions
- This prevents users from impersonating other users or manipulating attribution data

### Immutability

- Once set, the `created_by_user_id` field **never changes**
- Approval attribution fields are set once and remain immutable
- Updates to records do not affect attribution data

### Authorization

- Users can only create records in their own organization (tenant isolation)
- Approval permissions are enforced by the existing approval service
- Attribution data is read-only and cannot be modified by users

## Error Handling

### Missing Authentication

**Request:**
```bash
POST /invoices
# Missing Authorization header
```

**Response:** `401 Unauthorized`
```json
{
  "detail": "Not authenticated"
}
```

### Invalid User ID Filter

**Request:**
```bash
GET /invoices?created_by_user_id=invalid
```

**Response:** `422 Unprocessable Entity`
```json
{
  "detail": [
    {
      "loc": ["query", "created_by_user_id"],
      "msg": "value is not a valid integer",
      "type": "type_error.integer"
    }
  ]
}
```

### Record Not Found

**Request:**
```bash
GET /invoices/99999
```

**Response:** `404 Not Found`
```json
{
  "detail": "Invoice not found"
}
```

## Usage Examples

### cURL Examples

#### Create Invoice with Automatic Attribution
```bash
curl -X POST "http://localhost:8000/api/v1/invoices" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "number": "INV-002",
    "amount": 1500.00,
    "currency": "USD",
    "client_id": 789
  }'
```

#### Get Invoices Created by Specific User
```bash
curl -X GET "http://localhost:8000/api/v1/invoices?created_by_user_id=5" \
  -H "Authorization: Bearer <token>"
```

#### Approve Expense with Automatic Attribution
```bash
curl -X POST "http://localhost:8000/api/v1/approvals/123/approve" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Approved - complies with policy"
  }'
```

### Python Examples

```python
import requests

# Set up authentication
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

# Create expense (attribution automatic)
expense_data = {
    "amount": 75.50,
    "currency": "USD",
    "category": "Meals",
    "description": "Team lunch",
    "date": "2025-12-06"
}
response = requests.post(
    "http://localhost:8000/api/v1/expenses",
    headers=headers,
    json=expense_data
)
expense = response.json()
print(f"Created by: {expense['created_by_username']}")

# Get expenses created by current user
user_id = 7
response = requests.get(
    f"http://localhost:8000/api/v1/expenses?created_by_user_id={user_id}",
    headers=headers
)
expenses = response.json()

# Approve expense (attribution automatic)
approval_id = 123
response = requests.post(
    f"http://localhost:8000/api/v1/approvals/{approval_id}/approve",
    headers=headers,
    json={"notes": "Approved"}
)
approval = response.json()
print(f"Approved by: {approval['approved_by_username']}")
```

### JavaScript Examples

```javascript
// Set up authentication
const headers = {
  'Authorization': `Bearer ${accessToken}`,
  'Content-Type': 'application/json'
};

// Create invoice (attribution automatic)
const invoiceData = {
  number: 'INV-002',
  amount: 1500.00,
  currency: 'USD',
  client_id: 789
};

const response = await fetch('http://localhost:8000/api/v1/invoices', {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(invoiceData)
});

const invoice = await response.json();
console.log(`Created by: ${invoice.created_by_username}`);

// Get invoices created by specific user
const userId = 5;
const listResponse = await fetch(
  `http://localhost:8000/api/v1/invoices?created_by_user_id=${userId}`,
  { headers: headers }
);

const invoices = await listResponse.json();

// Reject expense (attribution automatic)
const approvalId = 124;
const rejectResponse = await fetch(
  `http://localhost:8000/api/v1/approvals/${approvalId}/reject`,
  {
    method: 'POST',
    headers: headers,
    body: JSON.stringify({
      reason: 'Missing receipt',
      notes: 'Please upload receipt and resubmit'
    })
  }
);

const rejection = await rejectResponse.json();
console.log(`Rejected by: ${rejection.rejected_by_username}`);
```

## Requirements Mapping

This API implementation satisfies all requirements from the User Attribution Tracking specification:

### Requirement 1: Creator Attribution
- **1.1-1.4**: Automatic capture of creator user ID for all entities
- **1.5**: Display creator name in API responses

### Requirement 2: Approval Attribution
- **2.1-2.4**: Automatic capture of approver/rejector user ID
- **2.5-2.6**: Display approver/rejector name in API responses

### Requirement 3: Automatic Capture
- **3.1-3.2**: User ID extracted from authenticated session
- **3.3**: Manual override prevented
- **3.4**: Unauthenticated requests rejected

### Requirement 4: Database Schema
- **4.1-4.5**: Attribution columns added to all tables
- **4.6-4.7**: Filtering by creator/approver supported

### Requirement 5: API Response Format
- **5.1-5.6**: All responses include attribution fields

### Requirement 6: UI Display
- **6.1-6.6**: Attribution data available for frontend display

### Requirement 7: Legacy Data Handling
- **7.1-7.4**: Graceful handling of missing attribution

## Testing

Test scripts are available to verify attribution functionality:

```bash
# Test invoice attribution
python api/tests/test_invoice_attribution_properties.py

# Test expense attribution
python api/tests/test_expense_attribution_properties.py

# Test bank statement attribution
python api/tests/test_bank_statement_attribution_properties.py

# Test approval attribution
python api/tests/test_approval_attribution_properties.py

# Test creator filtering
python api/tests/test_creator_attribution_filtering.py
```

## Support

- **API Documentation**: [https://docs.yourcompany.com/api](https://docs.yourcompany.com/api)
- **Developer Support**: [api-support@yourcompany.com](mailto:api-support@yourcompany.com)
- **Issue Tracker**: [https://github.com/yourcompany/issues](https://github.com/yourcompany/issues)
