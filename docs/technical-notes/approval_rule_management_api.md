# Approval Rule Management API

This document describes the approval rule management endpoints that were implemented as part of task 6 in the expense approval workflow specification.

## Overview

The approval rule management API provides CRUD operations for managing approval rules that determine which expenses require approval and who should approve them. These endpoints are restricted to administrators only.

## Endpoints

### Create Approval Rule
- **POST** `/api/v1/approvals/approval-rules`
- **Permission**: Admin only
- **Description**: Creates a new approval rule with configurable criteria
- **Request Body**: `ApprovalRuleCreate` schema
- **Response**: Created `ApprovalRule` object

### List Approval Rules
- **GET** `/api/v1/approvals/approval-rules`
- **Permission**: Non-viewer users
- **Description**: Lists approval rules with optional filtering and pagination
- **Query Parameters**:
  - `is_active` (optional): Filter by active status
  - `approver_id` (optional): Filter by approver ID
  - `limit` (optional): Maximum number of results (1-100)
  - `offset` (optional): Number of results to skip
- **Response**: Array of `ApprovalRule` objects

### Update Approval Rule
- **PUT** `/api/v1/approvals/approval-rules/{rule_id}`
- **Permission**: Admin only
- **Description**: Updates an existing approval rule
- **Path Parameters**: `rule_id` - ID of the rule to update
- **Request Body**: `ApprovalRuleUpdate` schema
- **Response**: Updated `ApprovalRule` object

### Delete Approval Rule
- **DELETE** `/api/v1/approvals/approval-rules/{rule_id}`
- **Permission**: Admin only
- **Description**: Deletes an approval rule (prevents deletion if used in active approvals)
- **Path Parameters**: `rule_id` - ID of the rule to delete
- **Response**: Success message

## Schema Details

### ApprovalRuleCreate
```json
{
  "name": "string",
  "min_amount": "number (optional, >= 0)",
  "max_amount": "number (optional, >= 0, > min_amount)",
  "category_filter": "string (optional, JSON array)",
  "currency": "string (default: USD)",
  "approval_level": "integer (default: 1, >= 1)",
  "approver_id": "integer (required)",
  "is_active": "boolean (default: true)",
  "priority": "integer (default: 0)",
  "auto_approve_below": "number (optional, >= 0)"
}
```

### ApprovalRuleUpdate
All fields are optional and only provided fields will be updated.

## Requirements Addressed

This implementation addresses the following requirements from the expense approval workflow specification:

- **Requirement 3.1**: Configuration of approval rules based on expense amount thresholds
- **Requirement 3.2**: Configuration based on expense categories
- **Requirement 3.3**: Assignment of users to approval roles with specific permissions
- **Requirement 7.1**: Assignment of approval permissions to specific users
- **Requirement 7.2**: Setting maximum approval amounts per user

## Security Features

- Admin-only access for create, update, and delete operations
- Validation of approver user existence
- Prevention of rule deletion when used in active approvals
- Comprehensive audit logging for all rule management operations
- Input validation and sanitization

## Error Handling

- **400 Bad Request**: Invalid input data or validation errors
- **403 Forbidden**: Insufficient permissions (non-admin users)
- **404 Not Found**: Approval rule not found
- **422 Unprocessable Entity**: Business logic violations (e.g., invalid approver ID)
- **500 Internal Server Error**: Unexpected system errors

## Testing

Comprehensive test coverage includes:
- CRUD operation tests for all endpoints
- Permission validation tests
- Input validation and error handling tests
- Integration tests for complete rule lifecycle
- Edge case and validation boundary tests