# Search Functionality Enhancement

## Summary
Enhanced the global search functionality to include **Inventory** and **Reminders** in addition to the existing search capabilities.

## What Was Changed

### Backend Changes

#### 1. `api/services/search_service.py`
- **Added imports**: `InventoryItem` and `Reminder` models
- **Updated entity types list**: Added `'inventory'` and `'reminders'` to all search operations
- **Added new mappings**:
  - Inventory mapping with fields: name, sku, description, category, quantity, unit_price, currency
  - Reminders mapping with fields: title, description, status, priority, due_date, assigned_to_name
- **Added indexing methods**:
  - `index_inventory_item()` - Indexes inventory items with searchable text
  - `index_reminder()` - Indexes reminders with searchable text
- **Enhanced database fallback search**:
  - Added inventory search by name, sku, and description
  - Added reminders search by title and description
- **Updated reindex_all()**: Now includes inventory items and reminders

#### 2. `api/routers/search.py`
- **Updated API documentation**: Added `inventory` and `reminders` to the types parameter description
- **Added URL routing**:
  - Inventory: `/inventory`
  - Reminders: `/reminders`
- **Enhanced result metadata**:
  - Inventory: Shows name, SKU, and quantity
  - Reminders: Shows title, priority, and status

### Frontend Changes

#### 3. `ui/src/components/search/SearchDialog.tsx`
- **Added icons**:
  - Inventory: `Package` icon (teal color)
  - Reminders: `Bell` icon (yellow color)
- **Updated placeholder text**: Now mentions inventory and reminders
- **Enhanced visual display**: Proper color coding for new entity types

## Supported Search Entities

The search now supports the following entities:

1. ✅ **Invoices** - Search by invoice number, client name, description
2. ✅ **Clients** - Search by name, email, company
3. ✅ **Payments** - Search by invoice number, payment method, notes
4. ✅ **Expenses** - Search by vendor, category, description
5. ✅ **Statements** - Search by filename, bank name, account number
6. ✅ **Attachments** - Search by filename, content
7. ✅ **Inventory** - Search by name, SKU, description, category (NEW)
8. ✅ **Reminders** - Search by title, description (NEW)

## How to Use

### Search Keyboard Shortcut
- **Mac**: `⌘ + K`
- **Windows/Linux**: `Ctrl + K`

### Search Examples
- Search for inventory: "laptop", "SKU-123", "electronics"
- Search for reminders: "follow up", "meeting", "deadline"
- Search across all: Type any keyword to search all entities

### API Usage
```bash
# Search all entities
GET /api/v1/search?q=laptop

# Search specific entities
GET /api/v1/search?q=laptop&types=inventory,reminders

# Limit results
GET /api/v1/search?q=laptop&limit=20
```

## Technical Details

### OpenSearch Integration
- Both inventory and reminders are indexed in OpenSearch when enabled
- Supports fuzzy matching and highlighting
- Tenant-isolated indices: `tenant_{id}_inventory` and `tenant_{id}_reminders`

### Database Fallback
- When OpenSearch is unavailable, searches use SQL LIKE queries
- Maintains functionality even without OpenSearch
- Searches across name, SKU, description for inventory
- Searches across title and description for reminders

### Reindexing
To reindex all data including new inventory and reminders:
```bash
POST /api/v1/search/reindex
```

## Benefits

1. **Unified Search**: Find inventory items and reminders alongside other business data
2. **Improved Productivity**: Quick access to inventory and task management
3. **Consistent UX**: Same search interface for all entity types
4. **Flexible**: Works with or without OpenSearch
5. **Scalable**: Supports large datasets with proper indexing

## Future Enhancements

Potential improvements:
- Add filters for inventory (by category, low stock)
- Add filters for reminders (by priority, status, due date)
- Add search suggestions specific to inventory and reminders
- Add advanced search operators
- Add search history and saved searches
