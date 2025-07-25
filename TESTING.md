# Testing Guide

This document provides comprehensive information about testing in the Invoice Management Application.

## 🧪 Test Structure

### API Tests (FastAPI + pytest)
- **Location**: `api/tests/`
- **Framework**: pytest with FastAPI TestClient
- **Database**: SQLite for testing (isolated from production)
- **Coverage**: pytest-cov for coverage reports

### UI Tests (React + Vitest)
- **Location**: `ui/src/components/__tests__/`, `ui/src/utils/__tests__/`
- **Framework**: Vitest with React Testing Library
- **Environment**: jsdom for DOM simulation
- **Coverage**: Vitest coverage with v8

## 🚀 Running Tests

### Quick Start - All Tests
```bash
# Run all tests (API + UI)
./run-tests.sh
```

### API Tests Only
```bash
cd api
./run-tests.sh

# Or manually:
pip install -r requirements.txt
pytest -v --cov=. --cov-report=html
```

### UI Tests Only
```bash
cd ui
./run-tests.sh

# Or manually:
npm install
npm run test:coverage
```

### Docker Environment
```bash
# API tests in Docker
docker-compose exec api pip install -r requirements.txt
docker-compose exec api pytest -v --cov=.

# UI tests in Docker
docker-compose exec ui npm install
docker-compose exec ui npm run test:coverage
```

## 📊 Coverage Reports

After running tests, coverage reports are generated:

- **API Coverage**: `api/htmlcov/index.html`
- **UI Coverage**: `ui/coverage/index.html`

## 🧪 Test Categories

### API Tests

#### Authentication Tests (`test_auth.py`)
- User signup
- User login
- JWT token validation

#### Client Management Tests (`test_clients.py`)
- Create client
- List clients
- Update client
- Delete client

#### Invoice Tests (`test_invoices.py`)
- Create invoice
- List invoices
- Update invoice status
- Invoice calculations

### UI Tests

#### Component Tests
- Button interactions
- Form validation
- Dashboard components
- Modal dialogs

#### Utility Tests
- Date formatting
- Currency formatting
- Validation helpers

## 🔧 Test Configuration

### API Configuration (`pytest.ini`)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
addopts = --cov=. --cov-report=html --cov-report=term-missing
```

### UI Configuration (`vite.config.ts`)
```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.ts'],
}
```

## 📝 Writing Tests

### API Test Example
```python
def test_create_client(client: TestClient, auth_headers):
    response = client.post(
        "/api/v1/clients/",
        json={
            "name": "Test Client",
            "email": "client@example.com"
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Test Client"
```

### UI Test Example
```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from '../ui/button'

test('button handles click', async () => {
  const handleClick = vi.fn()
  render(<Button onClick={handleClick}>Click me</Button>)
  
  await userEvent.click(screen.getByRole('button'))
  expect(handleClick).toHaveBeenCalled()
})
```

## 🎯 Test Best Practices

### API Tests
- Use test database (SQLite) for isolation
- Mock external services (email, payment providers)
- Test both success and error scenarios
- Use fixtures for common setup
- Test authentication and authorization

### UI Tests
- Test user interactions, not implementation details
- Use React Testing Library queries
- Mock API calls with MSW or similar
- Test accessibility features
- Focus on user behavior

## 🔄 Continuous Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run API Tests
        run: |
          cd api
          pip install -r requirements.txt
          pytest
      - name: Run UI Tests
        run: |
          cd ui
          npm install
          npm run test:coverage
```

## 🐛 Debugging Tests

### API Test Debugging
```bash
# Run specific test
pytest tests/test_auth.py::test_login -v

# Run with pdb debugger
pytest --pdb tests/test_auth.py

# Show print statements
pytest -s tests/test_auth.py
```

### UI Test Debugging
```bash
# Run specific test
npm run test -- Button.test.tsx

# Run in watch mode
npm run test -- --watch

# Run with UI
npm run test:ui
```

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Vitest Documentation](https://vitest.dev/)

## 🤝 Contributing Tests

When adding new features:

1. **Write tests first** (TDD approach)
2. **Test both happy path and edge cases**
3. **Maintain high coverage** (aim for >80%)
4. **Update this documentation** if adding new test patterns
5. **Run all tests** before submitting PR

## 🚨 Common Issues

### API Tests
- **Database connection errors**: Ensure test database is properly configured
- **Authentication failures**: Check JWT token generation in fixtures
- **Import errors**: Verify Python path and module imports

### UI Tests
- **Component not found**: Check if component is properly exported
- **Async issues**: Use `await` with user interactions
- **Provider errors**: Ensure test utilities wrap components with providers

---

Happy Testing! 🎉