# Implementation Plan: Agentic AI Assistant

## Overview

This implementation plan breaks down the Agentic AI Assistant feature into discrete, incremental coding tasks. The approach follows a bottom-up strategy: first implementing core backend services, then extending the API, followed by frontend components, and finally integration and testing. Each task builds on previous work, ensuring no orphaned code.

## Tasks

- [ ] 1. Set up database schema and models
  - Create database migration for AI chat history extensions (conversation_id, mode, sections, metadata columns)
  - Create database migration for AI user preferences table
  - Update SQLAlchemy models to include new fields
  - _Requirements: 8.4, 6.4_

- [ ] 2. Implement Context Manager service
  - [ ] 2.1 Create ConversationContext and AIUserPreference Pydantic models
    - Define ConversationContext model with all required fields
    - Define AIUserPreference model for user settings
    - _Requirements: 8.3, 6.4_
  
  - [ ] 2.2 Implement ContextManager class with database operations
    - Implement load_context() method to retrieve conversation from database
    - Implement save_context() method to persist conversation
    - Implement add_message() method to append messages to context
    - Implement get_user_preferences() and save_user_preference() methods
    - _Requirements: 8.1, 8.4, 8.5, 6.4_
  
  - [ ]* 2.3 Write property test for context persistence
    - **Property 26: Context Database Persistence**
    - **Validates: Requirements 8.4**
  
  - [ ]* 2.4 Write property test for new conversation isolation
    - **Property 27: New Conversation Isolation**
    - **Validates: Requirements 8.5**

- [ ] 3. Implement Response Parser service
  - [ ] 3.1 Create ResponseSection Pydantic model
    - Define ResponseSection with type, content, and metadata fields
    - Add validation for section types
    - _Requirements: 7.1, 7.2_
  
  - [ ] 3.2 Implement ResponseParser class
    - Implement parse_stream() method to detect section markers in streaming text
    - Implement extract_plan_steps() to parse numbered steps from plan text
    - Implement extract_questions() to parse individual questions
    - Handle malformed responses gracefully with fallback to plain text
    - _Requirements: 7.1, 7.3, 7.4_
  
  - [ ]* 3.3 Write property test for structured response sections
    - **Property 21: Structured Response Sections**
    - **Validates: Requirements 7.1, 7.2, 7.5**
  
  - [ ]* 3.4 Write property test for logical section ordering
    - **Property 23: Logical Section Ordering**
    - **Validates: Requirements 7.4**

- [ ] 4. Implement Prompt Builder service
  - [ ] 4.1 Create PromptBuilder class with agentic prompt construction
    - Implement build_agentic_prompt() with system instructions for reasoning and planning
    - Include conversation context injection
    - Add user preference incorporation
    - _Requirements: 9.2, 1.1, 2.1_
  
  - [ ] 4.2 Implement specialized prompt methods
    - Implement build_clarification_prompt() for incorporating user answers
    - Implement build_execution_prompt() for approved plans
    - _Requirements: 3.4, 4.6_
  
  - [ ]* 4.3 Write property test for enhanced prompts in agentic mode
    - **Property 28: Enhanced Prompts in Agentic Mode**
    - **Validates: Requirements 9.2**

- [ ] 5. Implement Agentic Service
  - [ ] 5.1 Create AgenticService class with core processing logic
    - Initialize with database session and AI config
    - Integrate PromptBuilder, ResponseParser, and ContextManager
    - _Requirements: 1.1, 2.1, 3.1, 4.1_
  
  - [ ] 5.2 Implement process_request() method with streaming
    - Load or create conversation context
    - Build appropriate prompt based on mode
    - Call LiteLLM with streaming enabled
    - Parse streaming response into sections
    - Yield sections as they are identified
    - Save conversation context after completion
    - _Requirements: 1.1, 1.2, 7.3, 8.1_
  
  - [ ] 5.3 Implement handle_clarification_response() method
    - Load conversation context
    - Build clarification prompt with user answers
    - Process request with updated context
    - _Requirements: 3.4, 5.1_
  
  - [ ] 5.4 Implement handle_confirmation_response() method
    - Load conversation context
    - If approved, execute planned actions
    - If cancelled, abort and maintain state
    - Return execution results or cancellation message
    - _Requirements: 4.5, 4.6_
  
  - [ ]* 5.5 Write property test for streaming response delivery
    - **Property 2: Streaming Response Delivery**
    - **Validates: Requirements 1.2, 9.3**
  
  - [ ]* 5.6 Write property test for clarifying questions
    - **Property 8: Clarifying Questions for Incomplete Requests**
    - **Validates: Requirements 3.1, 3.2**
  
  - [ ]* 5.7 Write property test for confirmation on significant actions
    - **Property 11: Confirmation for Significant Actions**
    - **Validates: Requirements 4.1, 4.2, 4.3**

- [ ] 6. Checkpoint - Ensure backend services work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Extend AI chat router with agentic endpoint
  - [ ] 7.1 Create AgenticChatRequest Pydantic model
    - Add fields for mode, conversation_id, clarification_answers, confirmation_approved
    - Add validation for mode values
    - _Requirements: 6.1, 3.4, 4.5, 4.6_
  
  - [ ] 7.2 Implement /chat/agentic POST endpoint
    - Load AI configuration (with fallback to environment)
    - Initialize AgenticService
    - Route to appropriate handler based on request type (new, clarification, confirmation)
    - Return streaming response using FastAPI StreamingResponse
    - Handle errors gracefully with user-friendly messages
    - _Requirements: 9.1, 9.3, 9.4_
  
  - [ ] 7.3 Add error handling for common failure scenarios
    - Handle AI provider failures
    - Handle streaming interruptions
    - Handle context retrieval failures
    - Log all errors with full context
    - _Requirements: 9.5_
  
  - [ ]* 7.4 Write property test for backward compatibility
    - **Property 29: Backward Compatibility**
    - **Validates: Requirements 9.4**
  
  - [ ]* 7.5 Write unit tests for error scenarios
    - Test AI provider unavailable
    - Test invalid response format handling
    - Test context retrieval failure handling

- [ ] 8. Implement frontend mode toggle component
  - [ ] 8.1 Create ModeToggle component
    - Create component with simple/agentic mode buttons
    - Add visual styling to indicate active mode
    - Emit mode change events
    - _Requirements: 6.1_
  
  - [ ] 8.2 Add mode persistence logic
    - Load mode preference from localStorage on mount
    - Save mode preference to localStorage on change
    - _Requirements: 6.4_
  
  - [ ]* 8.3 Write property test for mode preference persistence
    - **Property 19: Mode Preference Persistence**
    - **Validates: Requirements 6.4**

- [ ] 9. Implement frontend response section components
  - [ ] 9.1 Create ReasoningDisplay component
    - Display thinking section with distinct styling
    - Show loading indicator during streaming
    - Support markdown rendering
    - _Requirements: 1.1, 1.3, 1.4_
  
  - [ ] 9.2 Create PlanDisplay component
    - Render plan as numbered ordered list
    - Add collapse/expand functionality
    - Highlight steps requiring user interaction
    - _Requirements: 2.1, 2.4, 10.2_
  
  - [ ] 9.3 Create QuestionForm component
    - Display questions with input fields
    - Collect user answers
    - Submit answers to backend
    - _Requirements: 3.3, 10.3_
  
  - [ ] 9.4 Create ConfirmationDialog component
    - Display plan summary
    - Show approve and cancel buttons
    - Submit user decision to backend
    - _Requirements: 4.4, 10.4_
  
  - [ ]* 9.5 Write property test for markdown rendering
    - **Property 3: Markdown Rendering Support**
    - **Validates: Requirements 1.4**
  
  - [ ]* 9.6 Write property test for question input rendering
    - **Property 32: Question Input Rendering**
    - **Validates: Requirements 10.3**

- [ ] 10. Enhance AIAssistant component with agentic support
  - [ ] 10.1 Update message state to support AgenticMessage type
    - Add sections array to message interface
    - Add requiresClarification and requiresConfirmation flags
    - Add conversationId tracking
    - _Requirements: 7.1, 8.1_
  
  - [ ] 10.2 Implement streaming response handler
    - Connect to /chat/agentic endpoint with streaming
    - Parse server-sent events
    - Update UI as sections arrive
    - Handle streaming errors and interruptions
    - _Requirements: 1.2, 7.3_
  
  - [ ] 10.3 Implement clarification workflow
    - Detect when response requires clarification
    - Display QuestionForm component
    - Send answers back to backend
    - Continue conversation with updated context
    - _Requirements: 3.1, 3.4_
  
  - [ ] 10.4 Implement confirmation workflow
    - Detect when response requires confirmation
    - Display ConfirmationDialog component
    - Send user decision to backend
    - Display execution results or cancellation message
    - _Requirements: 4.1, 4.5, 4.6_
  
  - [ ] 10.5 Add mode-specific rendering logic
    - Render sections only in agentic mode
    - Use simple rendering in simple mode
    - Allow mode switching mid-conversation
    - _Requirements: 6.2, 6.3, 6.5_
  
  - [ ]* 10.6 Write property test for simple mode behavior
    - **Property 17: Simple Mode Excludes Agentic Features**
    - **Validates: Requirements 6.2**
  
  - [ ]* 10.7 Write property test for agentic mode behavior
    - **Property 18: Agentic Mode Includes Enhanced Features**
    - **Validates: Requirements 6.3**
  
  - [ ]* 10.8 Write property test for mid-conversation mode switching
    - **Property 20: Mid-Conversation Mode Switching**
    - **Validates: Requirements 6.5**

- [ ] 11. Checkpoint - Ensure frontend components work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement end-to-end integration
  - [ ] 12.1 Wire frontend to backend agentic endpoint
    - Update API client to support streaming
    - Add conversation ID management
    - Handle authentication and authorization
    - _Requirements: 8.1, 9.1_
  
  - [ ] 12.2 Add error handling and user feedback
    - Display error messages for failed requests
    - Show retry options for recoverable errors
    - Handle timeout scenarios gracefully
    - _Requirements: 9.3_
  
  - [ ]* 12.3 Write integration tests for complete workflows
    - Test reasoning → answer flow
    - Test reasoning → planning → confirmation → execution flow
    - Test clarification → answer flow
    - Test mode switching during conversation

- [ ] 13. Implement property-based tests for remaining properties
  - [ ]* 13.1 Write property test for multi-step plan generation
    - **Property 4: Multi-Step Plan Generation**
    - **Validates: Requirements 2.1**
  
  - [ ]* 13.2 Write property test for entity references in plans
    - **Property 5: Entity References in Plans**
    - **Validates: Requirements 2.3**
  
  - [ ]* 13.3 Write property test for plan refinement
    - **Property 7: Plan Refinement with Context Preservation**
    - **Validates: Requirements 2.5, 5.1, 5.2**
  
  - [ ]* 13.4 Write property test for answer integration
    - **Property 10: Answer Integration into Context**
    - **Validates: Requirements 3.4**
  
  - [ ]* 13.5 Write property test for cancellation preserves state
    - **Property 12: Cancellation Preserves State**
    - **Validates: Requirements 4.5**
  
  - [ ]* 13.6 Write property test for approval executes actions
    - **Property 13: Approval Executes Actions**
    - **Validates: Requirements 4.6**
  
  - [ ]* 13.7 Write property test for preference memory
    - **Property 14: Preference Memory**
    - **Validates: Requirements 5.3**
  
  - [ ]* 13.8 Write property test for context persistence
    - **Property 24: Context Persistence Across Messages**
    - **Validates: Requirements 8.1, 8.2**
  
  - [ ]* 13.9 Write property test for comprehensive context storage
    - **Property 25: Comprehensive Context Storage**
    - **Validates: Requirements 8.3**
  
  - [ ]* 13.10 Write property test for interaction logging
    - **Property 30: Interaction Logging**
    - **Validates: Requirements 9.5**

- [ ] 14. Add monitoring and logging
  - [ ] 14.1 Implement metrics collection
    - Track agentic mode usage percentage
    - Track average response time by mode
    - Track clarification and confirmation rates
    - Track error rates by type
    - _Requirements: 9.5_
  
  - [ ] 14.2 Add comprehensive logging
    - Log all agentic interactions with context
    - Log prompt construction for debugging
    - Log parsing failures with raw responses
    - Log user decisions (approve/cancel)
    - _Requirements: 9.5_
  
  - [ ]* 14.3 Write unit tests for logging functionality
    - Test that agentic interactions are logged
    - Test that errors are logged with context
    - Test that metrics are collected correctly

- [ ] 15. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based and unit tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation follows a bottom-up approach: backend services → API → frontend components → integration
