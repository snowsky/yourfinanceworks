# Inventory Management API Reference

## 📋 Overview

This document provides a comprehensive reference for all Inventory Management API endpoints. The inventory system provides full CRUD operations, bulk operations, analytics, and import/export functionality.

## 🔗 Base URL

All endpoints are available under:
```
https://your-api-domain/api/v1/inventory
```

## 📊 Categories API

### Create Category
```http
POST /api/v1/inventory/categories
```

**Request Body:**
```json
{
  "name": "Electronics",
  "description": "Electronic devices and accessories",
  "color": "#4A90E2",
  "is_active": true
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Electronics",
  "description": "Electronic devices and accessories",
  "color": "#4A90E2",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Bulk Create Categories
```http
POST /api/v1/inventory/categories/bulk
```

**Request Body:**
```json
[
  {
    "name": "Electronics",
    "description": "Electronic devices",
    "color": "#4A90E2"
  },
  {
    "name": "Office Supplies",
    "description": "Office supplies and stationery",
    "color": "#50C878"
  }
]
```

### Get Categories
```http
GET /api/v1/inventory/categories?active_only=true
```

### Get Category
```http
GET /api/v1/inventory/categories/{category_id}
```

### Update Category
```http
PUT /api/v1/inventory/categories/{category_id}
```

### Delete Category
```http
DELETE /api/v1/inventory/categories/{category_id}
```

---

## 📦 Items API

### Create Item
```http
POST /api/v1/inventory/items
```

**Request Body:**
```json
{
  "name": "Business Laptop",
  "description": "High-performance business laptop",
  "sku": "LT-001",
  "category_id": 1,
  "unit_price": 1299.99,
  "cost_price": 900.00,
  "currency": "USD",
  "track_stock": true,
  "current_stock": 25,
  "minimum_stock": 5,
  "unit_of_measure": "each",
  "item_type": "product",
  "is_active": true
}
```

### Bulk Create Items
```http
POST /api/v1/inventory/items/bulk
```

**Request Body:**
```json
[
  {
    "name": "Business Laptop",
    "sku": "LT-001",
    "unit_price": 1299.99,
    "track_stock": true,
    "current_stock": 25,
    "minimum_stock": 5
  },
  {
    "name": "Wireless Mouse",
    "sku": "MS-002",
    "unit_price": 29.99,
    "track_stock": true,
    "current_stock": 100,
    "minimum_stock": 10
  }
]
```

### Get Items
```http
GET /api/v1/inventory/items?skip=0&limit=50&query=laptop&category_id=1&track_stock=true
```

**Query Parameters:**
- `skip`: Pagination offset (default: 0)
- `limit`: Items per page (default: 100, max: 1000)
- `query`: Search term for name, SKU, or description
- `category_id`: Filter by category ID
- `item_type`: Filter by item type (product, material, service)
- `is_active`: Filter by active status
- `track_stock`: Filter by stock tracking
- `low_stock_only`: Show only low stock items
- `min_price`: Minimum unit price filter
- `max_price`: Maximum unit price filter

### Get Item
```http
GET /api/v1/inventory/items/{item_id}
```

### Update Item
```http
PUT /api/v1/inventory/items/{item_id}
```

### Delete Item
```http
DELETE /api/v1/inventory/items/{item_id}
```

---

## 📈 Stock Management API

### Adjust Stock
```http
POST /api/v1/inventory/items/{item_id}/stock/adjust?quantity=10&reason=Received%20new%20shipment
```

**Parameters:**
- `quantity`: Quantity to adjust (positive for increase, negative for decrease)
- `reason`: Reason for the adjustment

### Bulk Stock Movements
```http
POST /api/v1/inventory/stock-movements/bulk
```

**Request Body:**
```json
[
  {
    "item_id": 1,
    "movement_type": "adjustment",
    "quantity": 10,
    "unit_cost": 29.99,
    "reference_type": "manual",
    "notes": "Stock adjustment"
  },
  {
    "item_id": 2,
    "movement_type": "purchase",
    "quantity": 50,
    "unit_cost": 15.00,
    "reference_type": "expense",
    "reference_id": 123
  }
]
```

### Get Stock Movements
```http
GET /api/v1/inventory/items/{item_id}/stock/movements?limit=50&movement_type=sale
```

### Get Low Stock Alerts
```http
GET /api/v1/inventory/stock/low-stock
```

### Get Recent Movements
```http
GET /api/v1/inventory/movements/recent?days=7&limit=50
```

---

## 📊 Analytics & Reporting API

### Get Inventory Analytics
```http
GET /api/v1/inventory/analytics
```

**Response:**
```json
{
  "total_items": 150,
  "active_items": 145,
  "low_stock_items": 12,
  "total_value": 250000.00,
  "currency": "USD"
}
```

### Value Report
```http
GET /api/v1/inventory/reports/value
```

### Profitability Analysis
```http
GET /api/v1/inventory/reports/profitability?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T23:59:59Z
```

### Turnover Analysis
```http
GET /api/v1/inventory/reports/turnover?months=12
```

### Category Performance
```http
GET /api/v1/inventory/reports/categories?start_date=2024-01-01T00:00:00Z
```

### Sales Velocity Report
```http
GET /api/v1/inventory/reports/sales-velocity?days=30
```

### Dashboard Data
```http
GET /api/v1/inventory/reports/dashboard
```

### Stock Movement Summary
```http
GET /api/v1/inventory/reports/stock-movements?item_id=1&days=30
```

---

## 🔗 Integration APIs

### Invoice Integration

#### Populate Invoice Item
```http
POST /api/v1/inventory/invoice-items/populate
```

**Request Body:**
```json
{
  "inventory_item_id": 1,
  "quantity": 2
}
```

#### Validate Stock for Invoice
```http
POST /api/v1/inventory/invoice-items/validate-stock
```

**Request Body:**
```json
{
  "invoice_items": [
    {
      "inventory_item_id": 1,
      "quantity": 5
    }
  ]
}
```

#### Get Invoice Inventory Summary
```http
GET /api/v1/inventory/invoice/{invoice_id}/inventory-summary
```

### Expense Integration

#### Create Inventory Purchase
```http
POST /api/v1/inventory/expenses/purchase
```

**Request Body:**
```json
{
  "vendor": "Office Depot",
  "reference_number": "PO-2024-001",
  "purchase_date": "2024-01-15",
  "currency": "USD",
  "items": [
    {
      "item_id": 1,
      "quantity": 25,
      "unit_cost": 4.99
    }
  ],
  "notes": "Office supplies purchase"
}
```

#### Get Purchase Summary
```http
GET /api/v1/inventory/expenses/purchase-summary?start_date=2024-01-01&end_date=2024-01-31&vendor=Office%20Depot
```

#### Get Expense Inventory Summary
```http
GET /api/v1/inventory/expense/{expense_id}/inventory-summary
```

---

## 📥📤 Import/Export API

### Import CSV
```http
POST /api/v1/inventory/import/csv
```

**Content-Type:** `multipart/form-data`

**Form Data:**
- `file`: CSV file with inventory data

**CSV Format:**
```csv
name,sku,description,category,unit_price,cost_price,currency,track_stock,current_stock,minimum_stock,unit_of_measure,item_type
Business Laptop,LT-001,High-performance laptop,Electronics,1299.99,900.00,USD,true,25,5,each,product
Wireless Mouse,MS-002,Ergonomic wireless mouse,Electronics,29.99,15.00,USD,true,100,10,each,product
```

**Response:**
```json
{
  "message": "Successfully imported 2 items",
  "imported_items": [...],
  "total_lines": 2,
  "successful_imports": 2
}
```

### Export CSV
```http
GET /api/v1/inventory/export/csv?include_inactive=false&category_id=1
```

**Query Parameters:**
- `include_inactive`: Include inactive items (default: false)
- `category_id`: Filter by category ID

**Response:** CSV file download with `Content-Disposition: attachment; filename=inventory_export.csv`

---

## 🔐 Authentication

All endpoints require authentication via JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## 📋 Response Format

### Success Response
```json
{
  "data": {...},
  "message": "Operation successful",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Error Response
```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 🚨 Error Codes

| Error Code | Description | HTTP Status |
|------------|-------------|-------------|
| `ITEM_NOT_FOUND` | Inventory item not found | 404 |
| `CATEGORY_NOT_FOUND` | Category not found | 404 |
| `INSUFFICIENT_STOCK` | Not enough stock available | 400 |
| `DUPLICATE_SKU` | SKU already exists | 409 |
| `DUPLICATE_CATEGORY` | Category name already exists | 409 |
| `ITEM_IN_USE` | Item cannot be deleted (has references) | 400 |
| `INVALID_FILE_FORMAT` | Invalid file format for import | 400 |
| `IMPORT_VALIDATION_FAILED` | Import data validation failed | 400 |
| `EXPORT_FAILED` | Export operation failed | 500 |

## 📊 Rate Limits

- **Standard endpoints:** 100 requests per minute
- **Bulk operations:** 20 requests per minute
- **Import/Export:** 10 requests per minute

## 🔄 Bulk Operations

### Categories Bulk Creation
- **Max items:** 100 categories per request
- **Validation:** Category names must be unique
- **Rollback:** If any category fails, entire operation rolls back

### Items Bulk Creation
- **Max items:** 500 items per request
- **Validation:** SKU must be unique, required fields validated
- **Stock updates:** Automatic stock movements created for tracked items

### Stock Movements Bulk Creation
- **Max movements:** 1000 movements per request
- **Validation:** Item existence, stock availability for decreases
- **Audit trail:** All movements logged with user information

## 📋 Data Validation Rules

### Item Validation
- `name`: Required, 1-255 characters
- `unit_price`: Required, >= 0
- `cost_price`: Optional, >= 0, must be <= unit_price
- `current_stock`: Required if track_stock=true, >= 0
- `minimum_stock`: Required if track_stock=true, >= 0
- `sku`: Optional, unique across all items
- `unit_of_measure`: Required, max 20 characters

### Category Validation
- `name`: Required, 1-100 characters, unique
- `description`: Optional, max 500 characters
- `color`: Optional, valid hex color code

### Stock Movement Validation
- `quantity`: Required, can be positive or negative
- `movement_type`: Required, must be valid type
- `item_id`: Required, must exist
- For decreases: Must have sufficient stock (if tracked)

## 🔍 Search and Filtering

### Item Search
- **Full-text search:** Searches name, SKU, and description
- **Category filtering:** Filter by category ID
- **Status filtering:** Active/inactive items
- **Stock filtering:** Stock tracking status, low stock alerts
- **Price filtering:** Min/max unit price range

### Movement Search
- **Date range:** Filter by movement date
- **Type filtering:** Filter by movement type (purchase, sale, adjustment, etc.)
- **Item filtering:** Movements for specific item
- **User filtering:** Movements by specific user

## 📈 Analytics Data Structure

### Inventory Analytics Response
```json
{
  "total_items": 150,
  "active_items": 145,
  "inactive_items": 5,
  "low_stock_items": 12,
  "out_of_stock_items": 3,
  "total_value": 250000.00,
  "total_cost_value": 150000.00,
  "potential_profit": 100000.00,
  "currency": "USD",
  "last_updated": "2024-01-01T00:00:00Z"
}
```

### Profitability Analysis Response
```json
{
  "period": {
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-31T23:59:59Z"
  },
  "summary": {
    "total_revenue": 50000.00,
    "total_cost": 30000.00,
    "total_profit": 20000.00,
    "overall_margin_percent": 40.0
  },
  "items": [
    {
      "item_id": 1,
      "item_name": "Business Laptop",
      "sold_quantity": 10,
      "revenue": 12999.00,
      "cogs": 9000.00,
      "gross_profit": 3999.00,
      "gross_margin_percent": 30.8
    }
  ]
}
```

## 🔧 Maintenance Endpoints

### Health Check
```http
GET /api/v1/inventory/health
```

### Database Cleanup
```http
POST /api/v1/inventory/maintenance/cleanup
```

### Rebuild Search Index
```http
POST /api/v1/inventory/maintenance/reindex
```

## 📋 Usage Examples

### Creating a Complete Inventory Item
```bash
curl -X POST "/api/v1/inventory/items" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Premium Office Chair",
    "description": "Ergonomic office chair with lumbar support",
    "sku": "CHR-001",
    "category_id": 2,
    "unit_price": 299.99,
    "cost_price": 150.00,
    "currency": "USD",
    "track_stock": true,
    "current_stock": 25,
    "minimum_stock": 5,
    "unit_of_measure": "each",
    "item_type": "product",
    "is_active": true
  }'
```

### Bulk Importing Items via CSV
```bash
curl -X POST "/api/v1/inventory/import/csv" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@inventory_import.csv"
```

### Getting Low Stock Alerts
```bash
curl -X GET "/api/v1/inventory/stock/low-stock" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Exporting Inventory Data
```bash
curl -X GET "/api/v1/inventory/export/csv?include_inactive=false" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -o inventory_export.csv
```

---

*This API reference provides comprehensive documentation for all inventory management endpoints. For additional support or questions, please refer to the main Inventory Management System documentation.*
