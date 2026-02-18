# Implementation Plan: Context-Aware AI Assistant

## Overview

This implementation plan breaks down the Context-Aware AI Assistant feature into discrete, incremental tasks. The approach follows a bottom-up strategy: first implementing the core context detection hook, then extending the backend to accept context, then integrating context into the AI Assistant UI, and finally adding polish and testing.

## Tasks

- [ ] 1. Create usePageContext hook for context detection
  - Create `ui/src/hooks/usePageContext.ts` file
  - Implement route-to-page mapping configuration
  - Use `useLocation()` and `useSearchParams()` from react-router-dom
  - Extract route, pageName, pageType from current location
  - Extract filters and searchQuery from URL parameters
  - Return memoized PageContext object
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [ ]* 1.1 Write property test for context detection consistency
  - **Property 1: Context Detection Consistency**
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
  - Test that usePageContext returns valid context for any route
  - Use fast-check to generate random routes
  - Verify context always has route, pageName, and pageType fields

- [ ]* 1.2 Write unit tests for usePageContext hook
  - Test context extraction for /expenses route
  - Test context extraction for /invoices route
  - Test context extraction for /investments routes
  - Test filter extraction from URL parameters
  - Test search query extraction
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 2. Extend backend ChatRequest schema to support context
  - Open `api/commercial/ai/router.py`
  - Create `PageContext` Pydantic model with all required fields
  - Add optional `context` field to `ChatRequest` model
  - Ensure backward compatibility (context is optional)
  - _Requirements: 2.2, 2.3, 2.4, 7.2_

- [ ]* 2.1 Write property test for context transmission completeness
  - **Property 2: Context Transmission Completeness**
  - **Validates: Requirements 2.1, 2.2, 2.5**
  - Test that PageContext survives JSON serialization round-trip
  - Use Hypothesis to generate random PageContext objects
  - Verify serialization and deserialization preserve all fields

- [ ]* 2.2 Write property test for backward compatibility
  - **Property 3: Backward Compatibility Preservation**
  - **Validates: Requirements 2.4, 7.1, 7.2, 7.3, 7.4, 7.5**
  - Test that ChatRequest without context is valid
  - Test that backend processes requests without context
  - Use Hypothesis to generate random messages and config IDs

- [ ] 3. Implement context-enhanced prompt builder
  - Create `build_context_enhanced_prompt()` function in `api/commercial/ai/router.py`
  - Accept user_message, optional context, and base_prompt parameters
  - Build context section describing page, filters, and search
  - Add interpretation guidance for generic terms based on page type
  - Return enhanced prompt string
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ]* 3.1 Write property test for context-aware prompt enhancement
  - **Property 4: Context-Aware Prompt Enhancement**
  - **Validates: Requirements 3.1, 3.2**
  - Test that valid context always enhances the prompt
  - Use Hypothesis to generate random messages and contexts
  - Verify enhanced prompt contains base prompt, message, and context info
  - Verify enhanced prompt is longer than base + message

- [ ]* 3.2 Write unit tests for prompt builder
  - Test prompt with expenses page context
  - Test prompt with invoices page context
  - Test prompt with investment page context
  - Test prompt with filters included
  - Test prompt with search query included
  - Test prompt without context (should return base + message)
  - _Requirements: 3.3, 3.4, 3.5, 5.1, 5.2_

- [ ] 4. Modify ai_chat endpoint to use context
  - Update `ai_chat()` function in `api/commercial/ai/router.py`
  - Log context information when provided
  - Call `build_context_enhanced_prompt()` with request context
  - Use enhanced prompt for AI service call
  - Ensure existing functionality works without context
  - _Requirements: 2.3, 3.1, 7.1, 7.5_

- [ ]* 4.1 Write property test for error resilience
  - **Property 10: Error Resilience**
  - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
  - Test that malformed context doesn't crash the endpoint
  - Use Hypothesis to generate random dictionaries
  - Verify validation errors are caught gracefully
  - Verify processing continues without context on error

- [ ] 5. Checkpoint - Backend context support complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Create ContextBadge component for UI display
  - Create `ui/src/components/ai/ContextBadge.tsx` file
  - Accept PageContext as prop
  - Display page name with icon
  - Show active filters count if filters exist
  - Show search query badge if search is active
  - Style with Tailwind classes matching existing UI
  - _Requirements: 8.1, 8.2, 8.3, 8.5_

- [ ]* 6.1 Write unit tests for ContextBadge component
  - Test rendering with basic context (no filters/search)
  - Test rendering with filters
  - Test rendering with search query
  - Test rendering with both filters and search
  - _Requirements: 8.1, 8.2, 8.3_

- [ ] 7. Integrate usePageContext into AIAssistant component
  - Open `ui/src/components/AIAssistant.tsx`
  - Import and call `usePageContext()` hook
  - Store context in component state
  - Import and render `ContextBadge` component in chat UI
  - Position badge near the top of the chat interface
  - _Requirements: 6.1, 6.5, 8.1_

- [ ] 8. Modify AIAssistant to send context with queries
  - Update all `api.post('/ai/chat', ...)` calls in AIAssistant
  - Include `context: pageContext` in request body
  - Ensure context is sent with every chat request
  - _Requirements: 2.1, 2.2_

- [ ]* 8.1 Write integration test for context transmission
  - Test that chat requests include context
  - Mock usePageContext to return test context
  - Trigger chat message send
  - Verify API call includes context in payload
  - _Requirements: 2.1, 2.2_

- [ ] 9. Implement context update on navigation
  - Ensure usePageContext updates when route changes
  - Update ContextBadge display when context changes
  - Add visual indication when context changes during chat
  - _Requirements: 6.2, 6.3, 6.4, 8.5_

- [ ]* 9.1 Write unit test for context update behavior
  - Test that context updates when route changes
  - Test that context display updates immediately
  - Test that notification is shown on context change
  - _Requirements: 6.3, 6.4, 8.5_

- [ ] 10. Add error handling for context detection failures
  - Wrap context detection in try-catch in usePageContext
  - Return minimal context on error (route="unknown")
  - Log warning but don't block chat functionality
  - Ensure queries can be sent without context on error
  - _Requirements: 9.1, 9.3_

- [ ] 11. Add error handling for context validation failures
  - Add try-except around context processing in backend
  - Log validation errors with details
  - Fall back to processing without context on error
  - Ensure response is still successful
  - _Requirements: 9.2, 9.4, 9.5_

- [ ]* 11.1 Write unit tests for error handling
  - Test frontend handles context detection failure
  - Test backend handles malformed context
  - Test backend handles null/undefined context
  - Test that errors don't prevent query submission
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 12. Checkpoint - Core functionality complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Add context support for Expenses page
  - Verify usePageContext detects /expenses route correctly
  - Test filter extraction (category, label, unlinkedOnly)
  - Test search query extraction
  - Test with active filters and search
  - _Requirements: 4.1, 5.1, 5.2, 5.4, 5.5_

- [ ] 14. Add context support for Invoices page
  - Verify usePageContext detects /invoices route correctly
  - Test filter extraction (status, label)
  - Test search query extraction
  - Test with selected invoices
  - _Requirements: 4.2, 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 15. Add context support for Investment pages
  - Verify usePageContext detects /investments route correctly
  - Verify context for /investments/portfolio/:id route
  - Verify context for /investments/portfolio/:id/performance route
  - Test filter extraction (type, label)
  - Test metadata extraction (portfolioId, portfolioName)
  - _Requirements: 4.3, 4.4, 4.5, 5.1, 5.4_

- [ ]* 15.1 Write integration tests for multi-page support
  - Test context detection on Expenses page
  - Test context detection on Invoices page
  - Test context detection on Investment Dashboard
  - Test context detection on Portfolio Detail page
  - Test context detection on Portfolio Performance page
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 16. Optimize context detection performance
  - Memoize context object in usePageContext
  - Only recompute when route or search params change
  - Measure context detection time (should be < 50ms)
  - Ensure context doesn't block UI rendering
  - _Requirements: 10.1, 10.2, 10.5_

- [ ]* 16.1 Write property test for performance efficiency
  - **Property 11: Performance Efficiency**
  - **Validates: Requirements 10.2, 10.3, 10.4**
  - Test that context detection completes in < 50ms
  - Test that context payload size is minimal
  - Test that context processing adds < 100ms to response time

- [ ] 17. Add TypeScript types and documentation
  - Export PageContext interface from usePageContext
  - Add JSDoc comments to all functions
  - Document the route mapping configuration
  - Add usage examples in comments
  - _Requirements: All_

- [ ] 18. Update API documentation
  - Document the new context field in ChatRequest
  - Add example request payloads with context
  - Document the PageContext schema
  - Add notes about backward compatibility
  - _Requirements: 2.2, 7.1, 7.2_

- [ ] 19. Final checkpoint - All features complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 20. End-to-end integration test
  - Test complete flow: navigate to page → open chat → send query
  - Verify context is detected, transmitted, and used
  - Test on Expenses, Invoices, and Investment pages
  - Test with filters and search active
  - Test context updates when navigating during chat
  - _Requirements: All_

## Notes

- Tasks marked with `*` are optional testing tasks and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- The implementation follows a bottom-up approach: hook → backend → UI → integration
- Backward compatibility is maintained throughout (existing AI chat works without context)
