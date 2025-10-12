# Implementation Plan

- [x] 1. Create database models and schemas for approval workflow
  - Create ExpenseApproval model with relationships to expenses and users
  - Create ApprovalRule model with configurable approval criteria
  - Create ApprovalDelegate model for delegation functionality
  - Write Pydantic schemas for approval-related API requests and responses
  - _Requirements: 1.1, 2.1, 3.1, 7.1_

- [x] 2. Implement approval rule engine service
  - Create ApprovalRuleEngine class with expense evaluation logic
  - Implement rule matching based on amount thresholds and categories
  - Add support for multi-level approval workflows
  - Write unit tests for rule evaluation scenarios
  - _Requirements: 1.5, 3.1, 3.4_

- [x] 3. Create core approval service with workflow management
  - Implement ApprovalService class with submission and decision methods
  - Add expense status transition logic for approval workflow
  - Implement approval delegation functionality
  - Create approval history tracking and audit trail
  - Write unit tests for approval service methods
  - _Requirements: 1.1, 1.4, 2.3, 2.4, 5.5_

- [x] 4. Extend expense model with approval status support
  - Update Expense model to support new approval-related status values
  - Add database migration for new approval status values
  - Update existing expense endpoints to handle approval statuses
  - Write tests for expense status transitions
  - _Requirements: 1.1, 4.1, 4.4_

- [x] 5. Create approval REST API endpoints
  - Implement POST /expenses/{expense_id}/submit-approval endpoint
  - Create GET /approvals/pending endpoint for approver dashboard
  - Add POST /approvals/{approval_id}/approve endpoint
  - Implement POST /approvals/{approval_id}/reject endpoint
  - Create GET /approvals/history/{expense_id} endpoint
  - Write API tests for all approval endpoints
  - _Requirements: 1.1, 2.1, 2.3, 2.4, 4.1_

- [x] 6. Implement approval rule management endpoints
  - Create POST /approval-rules endpoint for rule creation (admin only)
  - Add GET /approval-rules endpoint for listing rules
  - Implement PUT /approval-rules/{rule_id} endpoint for updates
  - Add DELETE /approval-rules/{rule_id} endpoint
  - Write tests for approval rule CRUD operations
  - _Requirements: 3.1, 3.2, 3.3, 7.1, 7.2_

- [x] 7. Extend notification service for approval events
  - Add approval notification templates for submission, approval, and rejection
  - Implement notification triggers in approval service
  - Create reminder notification scheduling for pending approvals
  - Add escalation notifications for overdue approvals
  - Write tests for approval notification delivery
  - _Requirements: 1.4, 2.5, 5.1, 5.2, 5.4_

- [x] 8. Create approval permission system
  - Extend RBAC utilities with approval-specific permission checks
  - Implement approval limit validation based on user roles
  - Add permission checks for approval rule management
  - Create delegation permission validation
  - Write tests for approval permission enforcement
  - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [x] 9. Implement approval delegation functionality
  - Create POST /approvals/delegate endpoint for setting up delegates
  - Add GET /approvals/delegates endpoint for viewing delegations
  - Implement automatic delegation resolution in approval assignment
  - Add time-bounded delegation support with expiration
  - Write tests for delegation scenarios
  - _Requirements: 5.5, 7.4_

- [x] 10. Create approval dashboard UI components
  - Build ApprovalDashboard component showing pending approvals count
  - Create PendingApprovalsList component with filtering and sorting
  - Implement ApprovalActionButtons for approve/reject actions
  - Add ApprovalHistoryTimeline component for expense approval history
  - Write unit tests for approval UI components
  - _Requirements: 2.1, 2.2, 4.1, 4.2, 5.4_

- [x] 11. Implement expense approval status indicators
  - Create ExpenseApprovalStatus component for expense list display
  - Add approval status badges with appropriate colors and icons
  - Implement approval progress indicator for multi-level approvals
  - Create approval tooltip showing current approver and submission time
  - Write tests for status indicator components
  - _Requirements: 4.1, 4.2, 4.3_

- [x] 12. Build approval rule management interface
  - Create ApprovalRulesManager component for admin configuration
  - Implement ApprovalRuleForm for creating and editing rules
  - Add ApprovalRulesList with search and filter capabilities
  - Create rule priority management with drag-and-drop ordering
  - Write tests for approval rule management UI
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [x] 13. Implement approval delegation management UI
  - Create ApprovalDelegationManager component for setting up delegates
  - Add DelegationForm with date range picker and delegate selection
  - Implement ActiveDelegationsList showing current delegations
  - Create delegation status indicators and expiration warnings
  - Write tests for delegation management interface
  - _Requirements: 5.5, 7.4_

- [x] 14. Add approval workflow to expense submission flow
  - Update ExpenseForm to include approval submission option
  - Add validation for required fields when submitting for approval
  - Implement approval submission confirmation dialog
  - Create expense submission success notification with approval info
  - Write integration tests for expense submission with approval
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 15. Create approval reporting and analytics
  - Implement approval metrics calculation (average approval time, bottlenecks)
  - Create ApprovalReportsPage with approval analytics dashboard
  - Add approval compliance reporting for audit purposes
  - Implement approval pattern analysis and recommendations
  - Write tests for approval reporting functionality
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 16. Implement approval notification preferences
  - Extend user notification settings to include approval preferences
  - Add approval notification frequency configuration (immediate, daily digest)
  - Implement notification channel selection (email, in-app, both)
  - Create notification preference management UI
  - Write tests for approval notification preferences
  - _Requirements: 5.1, 5.2, 5.3_

- [x] 17. Add approval workflow error handling and validation
  - Implement comprehensive validation for approval submissions
  - Add error handling for approval permission violations
  - Create user-friendly error messages for approval workflow issues
  - Implement retry logic for failed approval notifications
  - Write tests for error scenarios and edge cases
  - _Requirements: 1.2, 2.6, 7.5_

- [x] 18. Create approval workflow integration tests
  - Write end-to-end tests for complete approval workflows
  - Test multi-level approval scenarios with different user roles
  - Implement approval delegation integration tests
  - Create performance tests for approval rule evaluation
  - Test approval notification delivery in integration scenarios
  - _Requirements: All requirements integration testing_

- [x] 19. Implement approval workflow database migrations
  - Create Alembic migration for ExpenseApproval table
  - Add migration for ApprovalRule table with indexes
  - Create migration for ApprovalDelegate table
  - Update existing expense status values migration
  - Test migration rollback scenarios
  - _Requirements: Database schema implementation_

- [x] 20. Add approval workflow documentation and help
  - Create user documentation for approval workflow features
  - Add admin guide for configuring approval rules
  - Implement in-app help tooltips for approval interface
  - Create API documentation for approval endpoints
  - Write troubleshooting guide for common approval issues
  - _Requirements: User experience and documentation_
