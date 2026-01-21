# TODO: AI Assistant Testing

## AI Intent Classification Testing

### Unit Tests Needed
- [ ] **Intent Classification Accuracy**
  - Test AI correctly classifies business queries into proper categories
  - Test edge cases and ambiguous queries
  - Test non-English queries if supported
  - Test very short vs very long queries

- [ ] **MCP Tool Routing**
  - Verify correct MCP tool is called based on classified intent
  - Test fallback to LLM for "general" intent classification
  - Test error handling when MCP tools fail

- [ ] **AI Configuration Management**
  - Test automatic default config setting for single active config
  - Test behavior when no AI config is available
  - Test behavior when multiple configs exist but none is default

### Integration Tests Needed
- [ ] **End-to-End Query Processing**
  - Test complete flow: user query → intent classification → MCP tool → response
  - Test various business query types (clients, invoices, payments, etc.)
  - Test response formatting and error handling

- [ ] **Authentication Integration**
  - Test JWT token creation and usage in MCP tools
  - Test token refresh and error handling
  - Test user permission validation

### Performance Tests Needed
- [ ] **Intent Classification Performance**
  - Measure response time for intent classification
  - Test with different AI providers (OpenAI, Ollama, etc.)
  - Test concurrent request handling

- [ ] **Memory Usage**
  - Monitor memory usage during AI classification
  - Test for memory leaks in long-running sessions

### Test Data Requirements
- [ ] **Sample Queries Dataset**
  - Create comprehensive dataset of business queries
  - Include variations and edge cases
  - Map expected intent classifications

- [ ] **Mock AI Responses**
  - Create mock responses for different AI providers
  - Test error scenarios and malformed responses

### Test Files to Create
- [ ] `api/tests/test_ai_intent_classification.py`
- [ ] `api/tests/test_ai_mcp_integration.py`
- [ ] `ui/src/components/__tests__/AIAssistant.test.tsx`
- [ ] `api/tests/test_ai_performance.py`

### Manual Testing Scenarios
- [ ] **Natural Language Variations**
  - "Show me my bank statements" vs "Display banking information"
  - "List expenses" vs "What did I spend money on?"
  - "Who owes me money?" vs "Outstanding balances"

- [ ] **Cross-Category Queries**
  - Queries that could match multiple categories
  - Queries with mixed business and general content

- [ ] **Error Scenarios**
  - AI service unavailable
  - Malformed AI responses
  - Network timeouts during classification

### Documentation Updates Needed
- [ ] Update API documentation with intent classification details
- [ ] Add troubleshooting guide for AI classification issues
- [ ] Document supported query patterns and examples
- [ ] Add performance benchmarks and recommendations

### Monitoring and Logging
- [ ] **Production Monitoring**
  - Track intent classification accuracy
  - Monitor AI service response times
  - Alert on classification failures

- [ ] **Debug Logging**
  - Log all intent classifications for analysis
  - Track MCP tool execution success/failure rates
  - Monitor user query patterns

## Priority
**High Priority**: Unit tests for intent classification and MCP tool routing
**Medium Priority**: Integration tests and performance testing
**Low Priority**: Advanced monitoring and analytics

## Estimated Effort
- Unit Tests: 2-3 days
- Integration Tests: 1-2 days  
- Performance Tests: 1 day
- Documentation: 1 day
- **Total**: ~5-7 days