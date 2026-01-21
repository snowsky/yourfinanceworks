# Invoice-Inventory Integration

This document outlines how invoices interact with the inventory management system in the invoice application.

## Overview

The system automatically manages inventory stock levels when invoices are created, completed, paid, cancelled, or refunded. This ensures inventory accuracy and prevents overselling.

## Stock Reduction on Invoice Completion

### Workflow

1. **Invoice Creation**
   - User creates invoice with line items referencing inventory items
   - System validates stock availability for each inventory item
   - Invoice can be saved even if stock is insufficient (warning shown)

2. **Invoice Completion/Payment**
   - When invoice status changes to "paid" or "completed"
   - System automatically creates stock movements to reduce inventory
   - Stock movements are created for each invoice item with inventory reference

3. **Stock Movement Details**
   - Movement type: "sale"
   - Quantity: negative value of invoice quantity
   - Reference: links to invoice ID
   - Notes: "Sale from invoice #[number]"

### Key Components

- **Invoice Service**: Manages invoice lifecycle
- **Inventory Integration Service**: `process_invoice_stock_movements()`
- **Stock Movement Service**: Creates inventory reduction movements

## Stock Reversal on Cancellation/Refund

### Workflow

1. **Invoice Cancellation/Refund**
   - When invoice is cancelled or refunded
   - System identifies all stock movements associated with the invoice
   - Creates reverse movements to restore inventory stock

2. **Reversal Process**
   - Finds all movements with `reference_type="invoice"` and `reference_id=invoice.id`
   - Creates new movements with opposite quantities
   - Movement type: "adjustment"
   - Notes: "Reversal of sale from cancelled invoice #[number]"

### Key Components

- **Inventory Integration Service**: `reverse_invoice_stock_movements()`
- **Audit Trail**: Maintains complete history of all stock changes

## Inventory Item References

### Invoice Line Items

Each invoice line item can optionally reference an inventory item:

```json
{
  "description": "Product Name",
  "quantity": 5,
  "price": 10.00,
  "amount": 50.00,
  "inventory_item_id": 123,
  "unit_of_measure": "pieces"
}
```

### Benefits

- **Automatic stock tracking**: Sales automatically reduce inventory
- **Cost tracking**: Purchase costs are maintained separately from sale prices
- **Reporting**: Inventory turnover and profit margins can be calculated
- **Validation**: System can warn about low stock or out-of-stock items

## Stock Availability Validation

### Pre-Invoice Validation

1. **Invoice Creation**
   - System checks stock availability for each inventory item
   - Shows warnings for insufficient stock
   - Allows invoice creation even with insufficient stock (backorders)

2. **Validation Details**
   - Checks `current_stock >= requested_quantity`
   - Only validates items that have `track_stock = true`
   - Returns detailed validation results per item

### Runtime Validation

- **Invoice Completion**: Validates stock before allowing status change
- **Real-time Updates**: Stock levels update immediately on invoice changes
- **Concurrency**: Handles concurrent invoice processing

## Data Flow

### Invoice Status Changes

```
Invoice Status Change → Inventory Integration Service → Stock Movement Creation → Database Update → Real-time Stock Updates
```

### Stock Validation

```
Invoice Save → Stock Validation → Availability Check → Warning/Error Response → User Notification
```

## Integration Points

- **Invoice Status Management**: Triggers stock movements on status changes
- **Inventory Service**: Provides stock availability and item details
- **Stock Movement Service**: Creates and manages all inventory movements
- **Audit Logging**: Tracks all inventory changes for compliance

## Error Handling

- **Insufficient Stock**: Warnings shown, but invoices can still be created
- **Movement Failures**: Logged but don't prevent invoice operations
- **Concurrency Issues**: Handled through database transactions
- **Data Integrity**: Stock movements are atomic with invoice status changes

## Business Rules

### Stock Reduction Timing

- Stock is only reduced when invoice is **paid** or **completed**
- Draft and sent invoices don't affect stock levels
- Allows for quotes and proposals without inventory commitment

### Reversal Conditions

- Stock is restored when invoice is **cancelled**
- Partial refunds may restore proportional stock amounts
- Complete reversals restore full quantities

### Validation Levels

- **Soft Validation**: Warnings for low stock
- **Hard Validation**: Prevents negative stock in some scenarios
- **Override Capability**: Admin users can force operations

## Future Enhancements

- **Stock Reservation**: Reserve stock when invoices are sent
- **Backorder Management**: Handle out-of-stock scenarios
- **Multi-location Inventory**: Support for multiple warehouses
- **Lot Tracking**: Track inventory by production lots
- **Serial Number Tracking**: Individual item tracking
