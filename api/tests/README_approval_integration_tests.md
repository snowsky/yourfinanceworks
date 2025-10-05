# Approval Workflow Integration Tests

This directory contains comprehensive integration tests for the expense approval workflow feature. These tests validate end-to-end approval workflows, multi-level approval scenarios, delegation functionality, performance characteristics, and error handling.

## Test Structure

### Core Test Modules

1. **`test_approval_workflow_integration.py`**
   - End-to-end approval workflow tests
   - Single and multi-level approval scenarios
   - Approval delegation integration
   - Auto-approval workflows
   - Notification integration testing

2. **`test_approval_workflow_edge_cases.py`**
   - Complex multi-level approval scenarios
   - Edge cases in approval rule matching
   - Error handling and recovery scenarios
   - Boundary conditions and validation
   - Circular delegation prevention

3. **`test_approval_workflow_performance.py`**
   - Performance benchmarks for approval rule evaluation
   - Scalability tests with large datasets
   - Concurrent approval processing performance
   - Memory usage optimization tests
   - Database query performance optimization

### Supporting Files

4. **`test_approval_integration_runner.py`**
   - Comprehensive test runner for all approval integration tests
   - Performance benchmark runner
   - Test coverage validation
   - Report generation

5. **`approval_integration_test_config.py`**
   - Shared configuration and utilities
   - Test data factories
   - Mock objects and fixtures
   - Custom assertions

## Test Coverage

### Requirements Coverage

The integration tests cover all requirements from the approval workflow specification:

#### Requirement 1: Employee Expense Submission
- ✅ Single-level approval workflow
- ✅ Multi-level approval workflow  
- ✅ Auto-approval for small expenses
- ✅ Validation of required fields
- ✅ Automatic approver assignment

#### Requirement 2: Manager Review and Approval
- ✅ Pending expense review
- ✅ Approval decision processing
- ✅ Rejection with reason
- ✅ Multi-level routing
- ✅ Notification delivery

#### Requirement 3: Administrator Configuration
- ✅ Approval rule evaluation
- ✅ Category-based rules
- ✅ Multi-level workflows
- ✅ Fallback approver assignment
- ✅ Rule priority handling

#### Requirement 4: Status Tracking
- ✅ Approval status display
- ✅ Current approver identification
- ✅ Complete audit trail
- ✅ Status change history
- ✅ Rejection and resubmission

#### Requirement 5: Notification System
- ✅ Approval assignment notifications
- ✅ Reminder notifications
- ✅ Decision notifications
- ✅ Dashboard integration
- ✅ Delegation support

#### Requirement 6: Audit and Reporting
- ✅ Approval time metrics
- ✅ Complete audit trails
- ✅ Compliance reporting
- ✅ Bottleneck identification
- ✅ Pattern analysis

#### Requirement 7: Permission Management
- ✅ Role-based approval permissions
- ✅ Approval limit enforcement
- ✅ Permission conflict resolution
- ✅ Delegation permissions
- ✅ Access control validation

### Performance Requirements

The tests validate the following performance characteristics:

- **Rule Evaluation**: < 50ms per expense with 500+ rules
- **Bulk Submission**: < 50ms per expense for 200+ expenses
- **Concurrent Processing**: 90%+ success rate with 10+ concurrent users
- **Memory Usage**: < 150MB for processing 500+ expenses
- **Query Performance**: < 30ms per history query

## Running the Tests

### Run All Integration Tests

```bash
# Run all approval workflow integration tests
python api/tests/test_approval_integration_runner.py --category all --verbose

# Run specific test category
python api/tests/test_approval_integration_runner.py --category workflow
python api/tests/test_approval_integration_runner.py --category edge_cases
python api/tests/test_approval_integration_runner.py --category performance
```

### Run Performance Benchmarks

```bash
# Run performance benchmarks only
python api/tests/test_approval_integration_runner.py --benchmark

# Run performance tests with detailed output
pytest api/tests/test_approval_workflow_performance.py -v -s --durations=0
```

### Run Individual Test Modules

```bash
# Run core workflow tests
pytest api/tests/test_approval_workflow_integration.py -v

# Run edge case tests
pytest api/tests/test_approval_workflow_edge_cases.py -v

# Run performance tests
pytest api/tests/test_approval_workflow_performance.py -v -s
```

### Validate Test Coverage

```bash
# Validate requirement coverage
python api/tests/test_approval_integration_runner.py --coverage
```

## Test Data and Setup

### Database Setup

The tests use in-memory SQLite databases for isolation and speed. Each test module creates its own database instance with:

- Complete schema creation
- Performance-optimized indexes
- Isolated test data
- Automatic cleanup

### Test Data Factory

The `ApprovalTestDataFactory` provides standardized test data:

```python
# Create test users with different roles
users = factory.create_test_users(db_session, count=5)

# Create standard approval rules
rules = factory.create_approval_rules(db_session, users)

# Create test expenses
expenses = factory.create_test_expenses(db_session, user, count=10)

# Create approval delegations
delegations = factory.create_approval_delegations(db_session, users)
```

### Mock Services

The tests use comprehensive mocks for external dependencies:

```python
# Mock notification service
notification_service = ApprovalTestMocks.create_notification_service_mock()

# Mock approval service
approval_service = ApprovalTestMocks.create_approval_service_mock()
```

## Performance Benchmarks

### Rule Evaluation Performance

Tests approval rule evaluation with increasing numbers of rules:

- 10 rules: < 1ms per expense
- 100 rules: < 10ms per expense  
- 500 rules: < 50ms per expense
- 1000 rules: < 100ms per expense

### Concurrent Processing

Tests concurrent approval processing:

- 10 concurrent users: 95%+ success rate
- 50 concurrent expenses: < 15 seconds total time
- Memory usage: < 150MB for 500 expenses

### Scalability Metrics

- **Linear scaling**: Performance scales linearly with data size
- **Memory efficiency**: Constant memory usage per operation
- **Database optimization**: Efficient query patterns and indexing

## Error Scenarios

### Handled Error Cases

1. **No Matching Approval Rule**: Raises `NoApprovalRuleFound`
2. **Insufficient Permissions**: Raises `InsufficientApprovalPermissions`
3. **Already Approved**: Raises `ExpenseAlreadyApproved`
4. **Notification Failures**: Graceful degradation
5. **Database Constraints**: Proper rollback and error reporting
6. **Concurrent Modifications**: Optimistic locking and retry logic

### Recovery Scenarios

1. **Partial Workflow Completion**: Resume from last successful step
2. **Service Restart**: Maintain workflow state across restarts
3. **Rule Deactivation**: Continue with existing assignments
4. **User Deactivation**: Proper permission validation

## Continuous Integration

### Test Execution

The integration tests are designed for CI/CD environments:

- Fast execution (< 2 minutes for full suite)
- Isolated test data
- Comprehensive error reporting
- Performance regression detection

### Quality Gates

- **Test Coverage**: 100% requirement coverage
- **Performance**: All benchmarks must pass
- **Success Rate**: 100% test pass rate required
- **Memory Usage**: No memory leaks detected

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Ensure SQLite is available
   - Check file permissions for test databases

2. **Performance Test Failures**
   - May fail on slower systems
   - Adjust thresholds in `ApprovalTestConfig`

3. **Mock Service Issues**
   - Verify mock configurations
   - Check async/await patterns

### Debug Mode

Run tests with debug output:

```bash
pytest api/tests/test_approval_workflow_integration.py -v -s --tb=long
```

### Performance Profiling

Profile performance tests:

```bash
pytest api/tests/test_approval_workflow_performance.py --profile
```

## Contributing

### Adding New Tests

1. Follow the existing test structure
2. Use the provided test factories and mocks
3. Include performance assertions where appropriate
4. Update requirement coverage mapping
5. Add documentation for new test scenarios

### Test Naming Convention

- `test_<scenario>_<expected_outcome>`
- Use descriptive names that explain the test purpose
- Group related tests in the same class

### Performance Test Guidelines

- Always include performance thresholds
- Test with realistic data volumes
- Measure both time and memory usage
- Include scalability validation

## Reports

### Test Reports

Test execution generates detailed reports:

- `approval_integration_test_report.json`: Detailed test results
- Console output: Summary and performance metrics
- Coverage reports: Requirement coverage validation

### Performance Reports

Performance tests generate benchmark reports:

- Execution times for all operations
- Memory usage patterns
- Scalability analysis
- Regression detection

## Future Enhancements

### Planned Improvements

1. **Load Testing**: Higher volume performance tests
2. **Stress Testing**: System behavior under extreme load
3. **Chaos Testing**: Failure injection and recovery validation
4. **Security Testing**: Permission boundary validation
5. **Integration Testing**: External service integration validation

### Test Infrastructure

1. **Parallel Execution**: Run tests in parallel for faster feedback
2. **Test Data Management**: More sophisticated test data generation
3. **Performance Monitoring**: Continuous performance tracking
4. **Visual Reports**: Graphical test result presentation