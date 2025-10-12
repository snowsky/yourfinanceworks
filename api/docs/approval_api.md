# Expense Approval API Documentation

## Overview

The Expense Approval API provides endpoints for managing the expense approval workflow, including submitting expenses for approval, processing approval decisions, and configuring approval rules.

## Base URL

```
https://api.yourcompany.com/v1
```

## Authentication

All API endpoints require authentication using Bearer tokens:

```http
Authorization: Bearer <your-access-token>
```

## Endpoints

### Expense Approval Operations

#### Submit Expense for Approval

Submit an expense for approval workflow processing.

```http
POST /expenses/{expense_id}/submit-approval
```

**Parameters:**
- `expense_id` (path, required): The ID of the expense to submit

**Request Body:**
```json
{
  "notes": "Additional context for approvers (optional)"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "approval_id": 123,
    "expense_id": 456,
    "status": "pending_approval",
    "assigned_approver": {
      "id": 789,
      "name": "John Manager",
      "email": "john.manager@company.com"
    },
    "approval_level": 1,
    "submitted_at": "2024-01-15T10:30:00Z",
    "estimated_approval_time": "2024-01-17T10:30:00Z"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Expense missing required fields or already submitted
- `403 Forbidden`: User not authorized to submit this expense
- `404 Not Found`: Expense not found
- `422 Unprocessable Entity`: Expense violates approval rules

#### Get Pending Approvals

Retrieve expenses pending approval for the current user.

```http
GET /approvals/pending
```

**Query Parameters:**
- `limit` (optional): Number of results per page (default: 20, max: 100)
- `offset` (optional): Number of results to skip (default: 0)
- `sort_by` (optional): Sort field (`submitted_at`, `amount`, `employee_name`)
- `sort_order` (optional): Sort direction (`asc`, `desc`)
- `min_amount` (optional): Filter by minimum expense amount
- `max_amount` (optional): Filter by maximum expense amount
- `category` (optional): Filter by expense category
- `employee_id` (optional): Filter by specific employee

**Response:**
```json
{
  "success": true,
  "data": {
    "approvals": [
      {
        "approval_id": 123,
        "expense": {
          "id": 456,
          "amount": 150.00,
          "currency": "USD",
          "category": "Meals",
          "description": "Client dinner",
          "date": "2024-01-14",
          "employee": {
            "id": 789,
            "name": "Jane Employee",
            "email": "jane.employee@company.com"
          }
        },
        "submitted_at": "2024-01-15T10:30:00Z",
        "approval_level": 1,
        "days_pending": 2
      }
    ],
    "pagination": {
      "total": 15,
      "limit": 20,
      "offset": 0,
      "has_more": false
    }
  }
}
```

#### Approve Expense

Approve a pending expense.

```http
POST /approvals/{approval_id}/approve
```

**Parameters:**
- `approval_id` (path, required): The ID of the approval to process

**Request Body:**
```json
{
  "notes": "Approved - complies with policy"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "approval_id": 123,
    "status": "approved",
    "approved_at": "2024-01-15T14:30:00Z",
    "approver": {
      "id": 789,
      "name": "John Manager"
    },
    "next_approval": null,
    "expense_status": "approved"
  }
}
```

#### Reject Expense

Reject a pending expense with reason.

```http
POST /approvals/{approval_id}/reject
```

**Parameters:**
- `approval_id` (path, required): The ID of the approval to reject

**Request Body:**
```json
{
  "reason": "Missing receipt for meal expense",
  "notes": "Please upload receipt and resubmit"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "approval_id": 123,
    "status": "rejected",
    "rejected_at": "2024-01-15T14:30:00Z",
    "rejection_reason": "Missing receipt for meal expense",
    "approver": {
      "id": 789,
      "name": "John Manager"
    },
    "expense_status": "rejected"
  }
}
```

#### Get Approval History

Retrieve the complete approval history for an expense.

```http
GET /approvals/history/{expense_id}
```

**Parameters:**
- `expense_id` (path, required): The ID of the expense

**Response:**
```json
{
  "success": true,
  "data": {
    "expense_id": 456,
    "current_status": "approved",
    "approval_history": [
      {
        "approval_id": 123,
        "approval_level": 1,
        "approver": {
          "id": 789,
          "name": "John Manager"
        },
        "status": "approved",
        "submitted_at": "2024-01-15T10:30:00Z",
        "decided_at": "2024-01-15T14:30:00Z",
        "notes": "Approved - complies with policy"
      }
    ],
    "total_approval_time": "4 hours 0 minutes"
  }
}
```

### Approval Rules Management

#### List Approval Rules

Get all approval rules (admin only).

```http
GET /approval-rules
```

**Query Parameters:**
- `active_only` (optional): Filter to active rules only (default: true)
- `category` (optional): Filter by expense category

**Response:**
```json
{
  "success": true,
  "data": {
    "rules": [
      {
        "id": 1,
        "name": "Manager Approval - Under $500",
        "min_amount": 0.01,
        "max_amount": 500.00,
        "currency": "USD",
        "category_filter": null,
        "approval_level": 1,
        "approver": {
          "id": 789,
          "name": "John Manager"
        },
        "priority": 10,
        "auto_approve_below": null,
        "is_active": true,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

#### Create Approval Rule

Create a new approval rule (admin only).

```http
POST /approval-rules
```

**Request Body:**
```json
{
  "name": "Director Approval - High Value",
  "min_amount": 500.01,
  "max_amount": 2000.00,
  "currency": "USD",
  "category_filter": ["Travel", "Equipment"],
  "approval_level": 1,
  "approver_id": 456,
  "priority": 20,
  "auto_approve_below": null,
  "is_active": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": 2,
    "name": "Director Approval - High Value",
    "min_amount": 500.01,
    "max_amount": 2000.00,
    "currency": "USD",
    "category_filter": ["Travel", "Equipment"],
    "approval_level": 1,
    "approver": {
      "id": 456,
      "name": "Jane Director"
    },
    "priority": 20,
    "auto_approve_below": null,
    "is_active": true,
    "created_at": "2024-01-15T15:00:00Z"
  }
}
```

#### Update Approval Rule

Update an existing approval rule (admin only).

```http
PUT /approval-rules/{rule_id}
```

**Parameters:**
- `rule_id` (path, required): The ID of the rule to update

**Request Body:** Same as create approval rule

#### Delete Approval Rule

Deactivate an approval rule (admin only).

```http
DELETE /approval-rules/{rule_id}
```

**Parameters:**
- `rule_id` (path, required): The ID of the rule to deactivate

### Approval Delegation

#### Create Delegation

Set up approval delegation.

```http
POST /approvals/delegate
```

**Request Body:**
```json
{
  "delegate_id": 456,
  "start_date": "2024-01-20",
  "end_date": "2024-01-25",
  "scope": {
    "max_amount": 1000.00,
    "categories": ["Travel", "Meals"],
    "all_approvals": false
  },
  "notify_delegator": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "delegation_id": 789,
    "approver_id": 123,
    "delegate": {
      "id": 456,
      "name": "Jane Delegate"
    },
    "start_date": "2024-01-20",
    "end_date": "2024-01-25",
    "scope": {
      "max_amount": 1000.00,
      "categories": ["Travel", "Meals"],
      "all_approvals": false
    },
    "is_active": true,
    "created_at": "2024-01-15T15:30:00Z"
  }
}
```

#### List Active Delegations

Get current user's active delegations.

```http
GET /approvals/delegations
```

**Response:**
```json
{
  "success": true,
  "data": {
    "delegations": [
      {
        "delegation_id": 789,
        "delegate": {
          "id": 456,
          "name": "Jane Delegate"
        },
        "start_date": "2024-01-20",
        "end_date": "2024-01-25",
        "scope": {
          "max_amount": 1000.00,
          "categories": ["Travel", "Meals"]
        },
        "is_active": true
      }
    ]
  }
}
```

#### Cancel Delegation

Cancel an active delegation.

```http
DELETE /approvals/delegations/{delegation_id}
```

### Approval Analytics

#### Get Approval Metrics

Retrieve approval performance metrics (admin/manager only).

```http
GET /approvals/analytics/metrics
```

**Query Parameters:**
- `start_date` (optional): Start date for metrics (ISO 8601)
- `end_date` (optional): End date for metrics (ISO 8601)
- `approver_id` (optional): Filter by specific approver
- `department` (optional): Filter by department

**Response:**
```json
{
  "success": true,
  "data": {
    "period": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    },
    "metrics": {
      "total_approvals": 150,
      "approved_count": 135,
      "rejected_count": 15,
      "average_approval_time_hours": 18.5,
      "approval_rate": 0.90,
      "bottlenecks": [
        {
          "approver": "John Manager",
          "pending_count": 8,
          "average_time_hours": 48.2
        }
      ]
    }
  }
}
```

## Error Handling

### Standard Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "APPROVAL_RULE_NOT_FOUND",
    "message": "No approval rule matches the expense criteria",
    "details": {
      "expense_id": 456,
      "amount": 150.00,
      "category": "Meals"
    }
  }
}
```

### Common Error Codes

- `EXPENSE_NOT_FOUND`: Expense does not exist
- `APPROVAL_NOT_FOUND`: Approval record does not exist
- `INSUFFICIENT_PERMISSIONS`: User lacks required permissions
- `EXPENSE_ALREADY_APPROVED`: Expense has already been approved
- `EXPENSE_ALREADY_REJECTED`: Expense has already been rejected
- `APPROVAL_RULE_NOT_FOUND`: No matching approval rule
- `INVALID_APPROVAL_LEVEL`: Approval level mismatch
- `DELEGATION_NOT_ACTIVE`: Delegation is not currently active
- `APPROVAL_DEADLINE_EXCEEDED`: Approval deadline has passed

## Rate Limiting

API requests are rate limited to prevent abuse:

- **Standard endpoints**: 100 requests per minute per user
- **Bulk operations**: 10 requests per minute per user
- **Admin endpoints**: 50 requests per minute per user

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
```

## Webhooks

Configure webhooks to receive real-time approval events:

### Webhook Events

- `expense.submitted_for_approval`
- `expense.approved`
- `expense.rejected`
- `approval.escalated`
- `delegation.created`
- `delegation.expired`

### Webhook Payload Example

```json
{
  "event": "expense.approved",
  "timestamp": "2024-01-15T14:30:00Z",
  "data": {
    "expense_id": 456,
    "approval_id": 123,
    "approver": {
      "id": 789,
      "name": "John Manager"
    },
    "approved_at": "2024-01-15T14:30:00Z"
  }
}
```

## SDK Examples

### JavaScript/Node.js

```javascript
const approvalAPI = require('@company/approval-api');

// Submit expense for approval
const approval = await approvalAPI.submitExpenseForApproval(456, {
  notes: 'Urgent approval needed'
});

// Get pending approvals
const pending = await approvalAPI.getPendingApprovals({
  limit: 10,
  sort_by: 'submitted_at',
  sort_order: 'desc'
});

// Approve expense
await approvalAPI.approveExpense(123, {
  notes: 'Approved - complies with policy'
});
```

### Python

```python
from approval_api import ApprovalClient

client = ApprovalClient(api_key='your-api-key')

# Submit expense for approval
approval = client.submit_expense_for_approval(
    expense_id=456,
    notes='Urgent approval needed'
)

# Get pending approvals
pending = client.get_pending_approvals(
    limit=10,
    sort_by='submitted_at',
    sort_order='desc'
)

# Approve expense
client.approve_expense(
    approval_id=123,
    notes='Approved - complies with policy'
)
```

## Testing

### Test Environment

Use the test environment for development and testing:

```
https://api-test.yourcompany.com/v1
```

### Test Data

Test environment includes sample data:
- Test expenses with various amounts and categories
- Test users with different approval permissions
- Pre-configured approval rules for testing

### Postman Collection

Download the Postman collection for easy API testing:
[Download Approval API Collection](./postman/approval-api-collection.json)

## Support

- **API Documentation**: [https://docs.yourcompany.com/api](https://docs.yourcompany.com/api)
- **Developer Support**: [api-support@yourcompany.com](mailto:api-support@yourcompany.com)
- **Status Page**: [https://status.yourcompany.com](https://status.yourcompany.com)
- **Community Forum**: [https://community.yourcompany.com](https://community.yourcompany.com)