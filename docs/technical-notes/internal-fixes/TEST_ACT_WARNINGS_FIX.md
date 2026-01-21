# Fixing React act() Warnings

## Problem
Tests show warnings like:
```
An update to ApprovalReportsPage inside a test was not wrapped in act(...)
```

## Solution Pattern

### Before (Causes Warning)
```typescript
it('updates state', () => {
  render(<Component />)
  fireEvent.click(screen.getByRole('button'))
  expect(screen.getByText('Updated')).toBeInTheDocument()
})
```

### After (Fixed)
```typescript
import { act } from '@testing-library/react'

it('updates state', async () => {
  render(<Component />)
  await act(async () => {
    fireEvent.click(screen.getByRole('button'))
  })
  expect(screen.getByText('Updated')).toBeInTheDocument()
})
```

## Common Scenarios

### 1. User Events
```typescript
import userEvent from '@testing-library/user-event'

it('handles user input', async () => {
  const user = userEvent.setup()
  render(<Component />)
  
  await user.click(screen.getByRole('button'))
  // userEvent already wraps in act()
  expect(screen.getByText('Result')).toBeInTheDocument()
})
```

### 2. Async Operations
```typescript
it('loads data', async () => {
  render(<Component />)
  
  await waitFor(() => {
    expect(screen.getByText('Loaded')).toBeInTheDocument()
  })
  // waitFor already wraps in act()
})
```

### 3. State Updates in Hooks
```typescript
import { act } from '@testing-library/react'

it('updates hook state', async () => {
  const { result } = renderHook(() => useState(false))
  
  await act(async () => {
    result.current[1](true)
  })
  
  expect(result.current[0]).toBe(true)
})
```

### 4. Multiple State Updates
```typescript
it('handles multiple updates', async () => {
  render(<Component />)
  
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /first/i }))
    fireEvent.click(screen.getByRole('button', { name: /second/i }))
  })
  
  expect(screen.getByText('Both clicked')).toBeInTheDocument()
})
```

## Files to Update

Priority order for fixing act() warnings:

1. `src/components/__tests__/ApprovalReportsPage.test.tsx` - Multiple warnings
2. `src/components/__tests__/ScheduledReportForm.test.tsx` - scrollIntoView error
3. `src/components/__tests__/InvoiceAttachmentPreview.test.tsx` - URL.createObjectURL error
4. `src/components/cookie-consent/__tests__/gdpr/GDPRCompliance.test.tsx` - Text matching error

## Quick Fix Script

```bash
# Find all test files with potential act() issues
grep -r "fireEvent\|setState" src --include="*.test.tsx" | grep -v "act("

# Run tests with verbose output to see warnings
npm run test:coverage -- --reporter=verbose
```

## Verification

After fixes, run:
```bash
npm run test:coverage
```

Expected result: No "act()" warnings in output
