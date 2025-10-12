# Implementation Plan

- [ ] 1. Set up database models and migrations for attachment system
  - Create ItemAttachment model with all required fields and relationships
  - Add attachment relationship to existing InventoryItem model
  - Create Alembic migration for item_attachments table with proper indexes
  - Write unit tests for model relationships and constraints
  - _Requirements: 1.1, 2.4, 3.6, 5.4_

- [ ] 2. Implement core file storage service
  - [ ] 2.1 Create FileStorageService class with secure file handling
    - Implement secure filename generation with UUID and sanitization
    - Create tenant-scoped directory structure (attachments/tenant_X/inventory/)
    - Add file validation methods for type, size, and content verification
    - Implement SHA-256 hash calculation for deduplication
    - Write unit tests for file storage operations
    - _Requirements: 2.1, 2.2, 5.1, 5.2, 5.4_

  - [ ] 2.2 Add file serving capabilities with security
    - Create secure file serving endpoint with authentication
    - Implement proper MIME type detection and headers
    - Add access control validation for tenant isolation
    - Create download and streaming response handlers
    - Write tests for file serving and security validation
    - _Requirements: 2.6, 5.3, 5.4_

- [ ] 3. Create image processing service for thumbnails and optimization
  - [ ] 3.1 Implement ImageProcessingService class
    - Add image validation and dimension detection
    - Create thumbnail generation for multiple sizes (150x150, 300x300)
    - Implement image optimization and compression
    - Add EXIF data removal for security
    - Write unit tests for image processing operations
    - _Requirements: 1.5, 1.6, 5.1_

  - [ ] 3.2 Create thumbnail storage and serving system
    - Implement organized thumbnail directory structure
    - Add thumbnail serving endpoint with caching headers
    - Create fallback thumbnail generation on demand
    - Add cleanup for orphaned thumbnail files
    - Write tests for thumbnail generation and serving
    - _Requirements: 1.5, 1.6_

- [ ] 4. Build attachment management service layer
  - [ ] 4.1 Create AttachmentService with core operations
    - Implement upload_attachment method with validation and processing
    - Add delete_attachment with file cleanup
    - Create update_attachment_metadata for description and ordering
    - Implement get_item_attachments with filtering
    - Add duplicate_check using file hash comparison
    - Write comprehensive unit tests for all service methods
    - _Requirements: 1.1, 1.3, 2.1, 2.2, 3.1, 3.2, 3.4, 3.5_

  - [ ] 4.2 Add image-specific management features
    - Implement set_primary_image with constraint enforcement
    - Create reorder_attachments for display order management
    - Add validation to ensure only one primary image per item
    - Implement attachment type filtering and organization
    - Write tests for image management operations
    - _Requirements: 1.4, 3.3_

- [ ] 5. Create API endpoints for attachment operations
  - [ ] 5.1 Build upload and basic CRUD endpoints
    - Create POST /api/inventory/{item_id}/attachments for file upload
    - Add GET /api/inventory/{item_id}/attachments for listing
    - Implement PUT /api/inventory/{item_id}/attachments/{attachment_id} for updates
    - Create DELETE /api/inventory/{item_id}/attachments/{attachment_id}
    - Add proper request validation and error handling
    - Write API integration tests for all endpoints
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 3.4, 3.5_

  - [ ] 5.2 Add specialized image management endpoints
    - Create POST /api/inventory/{item_id}/attachments/{attachment_id}/set-primary
    - Add POST /api/inventory/{item_id}/attachments/reorder
    - Implement GET /api/inventory/{item_id}/attachments/{attachment_id}/thumbnail/{size}
    - Create GET /api/inventory/{item_id}/attachments/{attachment_id}/download
    - Write tests for image-specific endpoints
    - _Requirements: 1.4, 1.6, 3.3_

- [ ] 6. Implement file validation and security measures
  - [ ] 6.1 Add comprehensive file validation
    - Create MIME type validation with magic number checking
    - Implement file size limits with early termination for large files
    - Add content scanning for malicious files
    - Create filename sanitization to prevent path traversal
    - Write security validation tests
    - _Requirements: 2.1, 2.2, 5.1, 5.2_

  - [ ] 6.2 Implement access control and audit logging
    - Add user permission validation for attachment operations
    - Create audit logging for upload, download, and delete operations
    - Implement IP address tracking for security
    - Add rate limiting for upload operations
    - Write tests for security controls
    - _Requirements: 5.3, 5.6_

- [ ] 7. Create frontend components for attachment management
  - [ ] 7.1 Build file upload component
    - Create drag-and-drop file upload interface
    - Add file type and size validation on client side
    - Implement upload progress indication
    - Create file preview functionality
    - Add error handling and user feedback
    - Write component unit tests
    - _Requirements: 1.1, 1.2, 2.1, 2.2_

  - [ ] 7.2 Create attachment gallery and management interface
    - Build image gallery component with thumbnail display
    - Add attachment list view with document icons
    - Implement drag-and-drop reordering for attachments
    - Create primary image selection interface
    - Add attachment metadata editing (description, document type)
    - Write tests for gallery and management components
    - _Requirements: 1.6, 3.1, 3.2, 3.3_

- [ ] 8. Add mobile camera integration
  - [ ] 8.1 Implement mobile camera capture
    - Add camera access and photo capture functionality
    - Create image cropping and rotation interface
    - Implement batch photo selection and upload
    - Add offline upload queue with sync capability
    - Write mobile-specific tests
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 8.2 Optimize mobile upload experience
    - Add automatic image compression for mobile uploads
    - Create upload progress tracking with cancellation
    - Implement background upload continuation
    - Add mobile-optimized error handling
    - Write mobile integration tests
    - _Requirements: 6.3, 6.4, 6.5_

- [ ] 9. Integrate attachments with inventory workflows
  - [ ] 9.1 Update inventory item display to show attachments
    - Modify inventory list to display thumbnail images
    - Add attachment count indicators to inventory items
    - Update inventory item detail view with attachment section
    - Create attachment filtering in inventory search
    - Write integration tests for inventory display updates
    - _Requirements: 1.6, 7.1, 7.4_

  - [ ] 9.2 Add attachment search and filtering capabilities
    - Implement search within attachment filenames and descriptions
    - Add filtering by attachment type (images, documents)
    - Create attachment metadata inclusion in global search
    - Add attachment indicators in search results
    - Write tests for search and filtering functionality
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 10. Implement invoice integration for product images
  - [ ] 10.1 Add product images to invoice generation
    - Modify invoice PDF generation to include product thumbnails
    - Create configurable setting for image inclusion in invoices
    - Add image display in invoice line item selection
    - Implement proper image sizing and quality for PDFs
    - Write tests for invoice image integration
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 10.2 Optimize invoice image performance
    - Add image caching for invoice generation
    - Implement lazy loading for invoice images
    - Create fallback handling for missing images
    - Add image compression for email-friendly invoice sizes
    - Write performance tests for invoice generation with images
    - _Requirements: 4.5, 4.6_

- [ ] 11. Add storage management and administration features
  - [ ] 11.1 Create storage usage tracking and reporting
    - Implement storage usage calculation per tenant
    - Add storage usage display in admin interface
    - Create storage usage reports by file type and date
    - Add storage quota enforcement with user notifications
    - Write tests for storage management features
    - _Requirements: 8.1, 8.2, 8.4, 8.5_

  - [ ] 11.2 Implement file cleanup and maintenance
    - Create orphaned file detection and cleanup jobs
    - Add automatic cleanup of old unused attachments
    - Implement file integrity checking and repair
    - Create backup integration for attachment files
    - Write tests for cleanup and maintenance operations
    - _Requirements: 5.5, 8.3, 8.6_

- [ ] 12. Add comprehensive error handling and logging
  - Create custom exception classes for attachment operations
  - Implement proper error responses with user-friendly messages
  - Add comprehensive logging for debugging and audit
  - Create error recovery mechanisms for failed operations
  - Write tests for error scenarios and recovery
  - _Requirements: All requirements - error handling is cross-cutting_

- [ ] 13. Create comprehensive test suite
  - Write integration tests for complete attachment workflows
  - Add performance tests for large file uploads and concurrent access
  - Create security tests for access control and validation
  - Implement end-to-end tests for mobile and web interfaces
  - Add load testing for file serving and thumbnail generation
  - _Requirements: All requirements - comprehensive testing coverage_

- [ ] 14. Update documentation and deployment
  - Create API documentation for attachment endpoints
  - Write user documentation for attachment features
  - Update deployment scripts to include attachment directories
  - Create backup procedures for attachment files
  - Add monitoring and alerting for attachment system health
  - _Requirements: All requirements - documentation and operational support_