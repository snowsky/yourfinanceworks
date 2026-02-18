# Requirements Document

## Introduction

The Context-Aware AI Assistant feature enhances the existing AI Assistant by automatically detecting which page or view the user is currently viewing in the application. This contextual information is sent with user queries to enable more natural, context-specific interactions without requiring users to explicitly specify what they're referring to.

For example, if a user is on the Expenses page and asks "add a label to the expenses uploaded today", the AI Assistant will understand they're referring to expenses on the current page. Similarly, on the Invoices page, "show me unpaid items" will be interpreted as referring to invoices.

## Glossary

- **AI_Assistant**: The existing AI chat system that processes user queries and provides responses
- **Page_Context**: Information about the current active page/route the user is viewing
- **Context_Payload**: The data structure containing page context information sent to the AI Assistant
- **Route**: The URL path that identifies which page the user is currently viewing
- **Frontend**: The React/TypeScript user interface application
- **Backend**: The Python FastAPI server that processes AI requests
- **Chat_Request**: The API request sent to the AI Assistant endpoint

## Requirements

### Requirement 1: Page Context Detection

**User Story:** As a user, I want the AI Assistant to automatically know which page I'm viewing, so that I don't have to specify context in my queries.

#### Acceptance Criteria

1. WHEN a user navigates to any page in the application, THE Frontend SHALL detect the current route
2. WHEN the route changes, THE Frontend SHALL update the stored page context information
3. THE Page_Context SHALL include the route path (e.g., "/expenses", "/invoices", "/investments")
4. THE Page_Context SHALL include a human-readable page name (e.g., "Expenses", "Invoices", "Investment Dashboard")
5. WHERE the page has filters or search parameters, THE Page_Context SHALL include active filter states

### Requirement 2: Context Transmission to AI Assistant

**User Story:** As a developer, I want page context to be sent with every AI query, so that the AI can interpret requests in the correct context.

#### Acceptance Criteria

1. WHEN a user submits a query to the AI_Assistant, THE Frontend SHALL include the Page_Context in the Chat_Request
2. THE Chat_Request SHALL extend the existing ChatRequest schema to include an optional context field
3. THE Backend SHALL accept and process the context field without breaking existing functionality
4. IF no context is provided, THEN THE Backend SHALL process the request normally (backward compatibility)
5. THE Context_Payload SHALL be structured as JSON with clearly defined fields

### Requirement 3: Context-Aware Query Processing

**User Story:** As a user, I want the AI to understand my queries based on the page I'm viewing, so that I can use natural language without being explicit.

#### Acceptance Criteria

1. WHEN the AI_Assistant receives a query with Page_Context, THE Backend SHALL include context information in the AI prompt
2. THE AI prompt SHALL be modified to include a context section describing the current page
3. WHEN processing queries on the Expenses page, THE AI_Assistant SHALL interpret references to "expenses" as referring to the current page's data
4. WHEN processing queries on the Invoices page, THE AI_Assistant SHALL interpret references to "invoices" as referring to the current page's data
5. WHEN processing queries on Investment pages, THE AI_Assistant SHALL interpret references to "portfolios" or "investments" as referring to the current page's data

### Requirement 4: Multi-Page Support

**User Story:** As a user, I want context awareness to work across all major pages in the application, so that I have a consistent experience.

#### Acceptance Criteria

1. THE Frontend SHALL support context detection for the Expenses page (/expenses)
2. THE Frontend SHALL support context detection for the Invoices page (/invoices)
3. THE Frontend SHALL support context detection for the Investment Dashboard page (/investments)
4. THE Frontend SHALL support context detection for the Investment Portfolio Detail page (/investments/portfolio/:id)
5. THE Frontend SHALL support context detection for the Investment Performance page (/investments/portfolio/:id/performance)
6. WHERE new pages are added, THE Frontend SHALL provide a mechanism to easily add context detection for those pages

### Requirement 5: Filter and Search Context

**User Story:** As a user, I want the AI to be aware of my current filters and search queries, so that it can provide more relevant responses.

#### Acceptance Criteria

1. WHEN a user has active filters on a page, THE Page_Context SHALL include the filter values
2. WHEN a user has an active search query, THE Page_Context SHALL include the search text
3. WHEN a user has selected specific items, THE Page_Context SHALL include the selection information
4. THE Context_Payload SHALL include a filters object containing all active filter states
5. THE Context_Payload SHALL include a search_query field when applicable

### Requirement 6: Context Persistence During Chat Session

**User Story:** As a user, I want the AI to remember the page context throughout our conversation, so that I don't have to repeat myself.

#### Acceptance Criteria

1. WHEN a user opens the AI chat interface, THE Frontend SHALL capture the current Page_Context
2. WHILE the chat interface remains open, THE Frontend SHALL maintain the initial Page_Context
3. IF the user navigates to a different page while the chat is open, THE Frontend SHALL update the Page_Context
4. WHEN the Page_Context changes during a chat session, THE Frontend SHALL notify the user of the context change
5. THE Frontend SHALL display the current page context in the chat interface

### Requirement 7: Backward Compatibility

**User Story:** As a developer, I want the context-aware feature to be backward compatible, so that existing AI functionality continues to work.

#### Acceptance Criteria

1. WHEN the Backend receives a Chat_Request without context, THE Backend SHALL process it using the existing logic
2. THE Backend SHALL not require the context field to be present in Chat_Request
3. WHEN the Frontend is on a page without context detection, THE AI_Assistant SHALL function normally
4. THE Backend SHALL handle null or undefined context values gracefully
5. THE existing AI_Assistant API endpoint SHALL remain unchanged in its core functionality

### Requirement 8: Context Display in UI

**User Story:** As a user, I want to see which page context the AI is using, so that I can verify it's interpreting my queries correctly.

#### Acceptance Criteria

1. WHEN the AI chat interface is open, THE Frontend SHALL display the current page context
2. THE context display SHALL show the page name in a clear, readable format
3. WHEN filters are active, THE context display SHALL indicate the active filters
4. THE context display SHALL be visually distinct but not intrusive
5. WHEN the context changes, THE Frontend SHALL update the context display immediately

### Requirement 9: Error Handling

**User Story:** As a user, I want the system to handle context errors gracefully, so that my AI experience is not disrupted.

#### Acceptance Criteria

1. IF the Frontend fails to detect page context, THEN THE Frontend SHALL send the query without context
2. IF the Backend receives malformed context data, THEN THE Backend SHALL log the error and process the query without context
3. WHEN context detection fails, THE Frontend SHALL not prevent the user from submitting queries
4. THE Backend SHALL validate context data structure before using it
5. IF context validation fails, THEN THE Backend SHALL continue processing with a warning logged

### Requirement 10: Performance Optimization

**User Story:** As a user, I want context detection to be fast and not slow down my interactions, so that the AI remains responsive.

#### Acceptance Criteria

1. THE Frontend SHALL detect page context without blocking the UI thread
2. THE context detection logic SHALL execute in less than 50ms
3. THE Context_Payload SHALL be kept minimal to reduce network overhead
4. THE Backend SHALL process context information without adding more than 100ms to response time
5. THE Frontend SHALL cache page context and only update when the route changes
