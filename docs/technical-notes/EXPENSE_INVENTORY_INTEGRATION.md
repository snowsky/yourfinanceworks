# Expense-Inventory Integration

This document outlines how expenses interact with the inventory management system in the invoice application.

## Overview

The system supports two types of inventory-related expenses:

1. **Inventory Consumption Expenses** - Expenses that consume (reduce) inventory stock
2. **Inventory Purchase Expenses** - Expenses that add inventory stock

## Inventory Consumption Expenses

### Workflow

1. **Expense Creation/Editing**
   - User checks "This expense is for consuming inventory items"
   - User selects inventory items and specifies quantities to consume
   - System automatically calculates expense amount based on item costs × quantities

2. **Validation**
   - Frontend validates that all consumption items have quantity > 0
   - Backend validates inventory items exist and quantities are valid
   - Stock availability is checked (though not strictly enforced for consumption)

3. **Stock Movement Creation**
   - When expense is saved, negative stock movements are created (quantity = -consumed_amount)
   - Movement type: "usage"
   - Reference: links back to the expense

4. **Amount Calculation**
   - Expense amount is automatically calculated: `Σ(quantity × unit_cost)` for all consumption items
   - Amount field becomes read-only when consumption is enabled

### Key Components

- **Frontend**: `InventoryConsumptionForm` component handles item selection and quantity input
- **Backend**: `InventoryIntegrationService.process_expense_inventory_consumption()`
- **Database**: `consumption_items` JSON field stores consumed items with quantities and costs

### Validation Rules

- Consumption must include at least one item
- Each item must have quantity > 0
- Items must exist in inventory
- Total consumption value determines expense amount

## Inventory Purchase Expenses

### Workflow

1. **Expense Creation/Editing**
   - User enables inventory purchase mode
   - User specifies items, quantities, and costs being purchased
   - System creates positive stock movements

2. **Validation**
   - All purchase items must have valid item_id and quantity > 0
   - Unit costs must be >= 0
   - Items must exist in inventory

3. **Stock Movement Creation**
   - Positive stock movements created (quantity = purchased_amount)
   - Movement type: "purchase"
   - Unit costs stored for inventory valuation

### Key Components

- **Frontend**: Purchase item selection and cost input forms
- **Backend**: `InventoryIntegrationService.process_expense_inventory_purchase()`
- **Database**: `inventory_items` JSON field stores purchased items

## Data Flow

### Saving an Expense

```
User Input → Frontend Validation → API Call → Backend Validation → Database Save → Stock Movement Creation
```

### Loading an Expense

```
Database Query → Expense Data + Consumption Items → Frontend State → Form Population
```

## Integration Points

- **Stock Movement Service**: Handles creation of all inventory movements
- **Inventory Service**: Validates item existence and stock levels
- **Currency Service**: Handles multi-currency calculations
- **Audit Logging**: All inventory changes are logged

## Error Handling

- Invalid quantities (< 0) are rejected at frontend and backend
- Non-existent inventory items cause validation errors
- Stock movement failures don't prevent expense saving (logged for later processing)
- Failed validations return appropriate error messages to user

## Future Enhancements

- Strict stock availability checking for consumption expenses
- Bulk inventory operations
- Inventory cost averaging
- Stock reservation system
