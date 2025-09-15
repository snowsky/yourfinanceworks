# Implementation Plan

- [ ] 1. Set up database models and schema
  - Create InventoryItem, InventoryCategory, and StockMovement models in models_per_tenant.py
  - Add foreign key relationships to existing InvoiceItem and Expense models
  - Write Alembic migration script for new inventory tables
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.2_

- [ ] 2. Create Pydantic schemas for API validation
  - Define InventoryItemCreate, InventoryItemUpdate, and InventoryItemResponse schemas
  - Create InventoryCategoryCreate, InventoryCategoryUpdate, and CategoryResponse schemas
  - Implement StockMovementCreate and StockMovementResponse schemas
  - Add validation rules for business constraints (positive prices, stock levels)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 3. Implement core inventory service layer
  - Create InventoryService class with CRUD operations for inventory items
  - Implement category management methods in InventoryService
  - Add search and filtering functionality for inventory items
  - Write unit tests for InventoryService methods
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 4. Implement stock movement service
  - Create StockMovementService class for tracking stock changes
  - Implement methods for recording stock movements (purchases, sales, adjustments)
  - Add stock level validation and low stock detection
  - Write unit tests for stock movement operations
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 5. Create inventory API router and endpoints
  - Implement inventory items CRUD endpoints (/api/inventory/items)
  - Create category management endpoints (/api/inventory/categories)
  - Add stock movement endpoints (/api/inventory/items/{id}/stock)
  - Implement search and filtering endpoints
  - Write API integration tests for all endpoints
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 6. Integrate inventory with invoice system
  - Modify InvoiceItem model to include inventory_item_id foreign key
  - Update invoice creation logic to populate from inventory items
  - Implement stock reduction when invoices are completed/paid
  - Add validation to prevent overselling when stock tracking is enabled
  - Write integration tests for invoice-inventory workflows
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 7. Integrate inventory with expense system
  - Add inventory purchase fields to Expense model
  - Implement expense processing to update inventory stock levels
  - Create logic to handle inventory purchase expenses
  - Add validation for inventory purchase expense data
  - Write integration tests for expense-inventory workflows
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 8. Create inventory management UI components
  - Build InventoryItemList component for displaying inventory items
  - Create InventoryItemForm component for adding/editing items
  - Implement CategoryManager component for category management
  - Add StockAdjustment component for manual stock adjustments
  - Write unit tests for all inventory UI components
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 9. Enhance invoice creation UI with inventory integration
  - Modify InvoiceItemForm to include inventory item selection
  - Add inventory item picker/search functionality
  - Display current stock levels when selecting inventory items
  - Show warnings for low stock or out-of-stock items
  - Update invoice line item display to show inventory item references
  - Write tests for enhanced invoice creation workflow
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 10. Enhance expense creation UI with inventory integration
  - Add inventory purchase option to expense creation form
  - Create inventory item selection for expense purchases
  - Implement quantity input for purchased inventory items
  - Add validation for inventory purchase expense data
  - Write tests for enhanced expense creation workflow
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 11. Implement inventory reporting and analytics
  - Create inventory value calculation methods
  - Implement low stock alerts and reporting
  - Add inventory movement reports with date filtering
  - Create profitability analysis comparing purchase vs sale prices
  - Integrate inventory data into existing reporting system
  - Write tests for inventory reporting functionality
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 12. Add materials and supplies tracking for service businesses
  - Implement item_type field to distinguish products from materials
  - Create project/client association for material usage tracking
  - Add material usage recording functionality
  - Implement material cost allocation to projects
  - Create material usage reports and project cost analysis
  - Write tests for materials tracking functionality
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [ ] 13. Implement comprehensive error handling and validation
  - Create inventory-specific exception classes
  - Add business rule validation (stock levels, pricing, etc.)
  - Implement proper error responses for API endpoints
  - Add client-side validation for inventory forms
  - Create error recovery mechanisms for failed operations
  - Write tests for error handling scenarios
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 14. Add inventory data export and import functionality
  - Implement CSV export for inventory items and stock movements
  - Create PDF export for inventory reports
  - Add bulk import functionality for inventory items
  - Implement data validation for imported inventory data
  - Create import/export UI components
  - Write tests for data import/export functionality
  - _Requirements: 6.5, 6.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 15. Implement inventory search and filtering
  - Add full-text search across inventory items
  - Implement category-based filtering
  - Create stock status filtering (in stock, low stock, out of stock)
  - Add price range and date range filtering
  - Integrate inventory search with global application search
  - Write tests for search and filtering functionality
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 16. Create inventory dashboard and analytics UI
  - Build inventory overview dashboard with key metrics
  - Create low stock alerts and notifications
  - Implement inventory value charts and trends
  - Add top-selling items and profitability analysis
  - Create inventory movement history visualization
  - Write tests for dashboard components and analytics
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 17. Add comprehensive testing and documentation
  - Write end-to-end tests for complete inventory workflows
  - Create API documentation for inventory endpoints
  - Add user documentation for inventory management features
  - Implement performance tests for inventory operations
  - Create migration guides for existing users
  - Write troubleshooting guides for common inventory issues
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [ ] 18. Implement final integration and system testing
  - Test complete inventory lifecycle (create → purchase → sell → report)
  - Validate data consistency across invoice, expense, and inventory systems
  - Perform load testing on inventory operations
  - Test multi-user scenarios and concurrent stock movements
  - Validate tenant isolation for inventory data
  - Create deployment scripts and database migration procedures
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_