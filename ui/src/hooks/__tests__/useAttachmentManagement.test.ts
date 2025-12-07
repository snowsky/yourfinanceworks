import { renderHook, waitFor, act } from '@testing-library/react'
import { vi } from 'vitest'
import { useAttachmentManagement } from '../useAttachmentManagement'

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

describe('useAttachmentManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with no attachment', () => {
    const { result } = renderHook(() => useAttachmentManagement())
    expect(result.current.invoiceAttachment).toBeNull()
  })

  it('handles file selection', async () => {
    const { result } = renderHook(() => useAttachmentManagement())
    const file = new File(['pdf content'], 'test.pdf', { type: 'application/pdf' })

    await act(async () => {
      result.current.handleFileSelect(file)
    })

    await waitFor(() => {
      expect(result.current.invoiceAttachment).toBeDefined()
    })
  })

  it('validates file type', async () => {
    const { result } = renderHook(() => useAttachmentManagement())
    const invalidFile = new File(['content'], 'test.txt', { type: 'text/plain' })

    await act(async () => {
      result.current.handleFileSelect(invalidFile)
    })

    expect(result.current.invoiceAttachment).toBeNull()
  })

  it('clears attachment', async () => {
    const { result } = renderHook(() => useAttachmentManagement())
    const file = new File(['pdf'], 'test.pdf', { type: 'application/pdf' })

    await act(async () => {
      result.current.handleFileSelect(file)
    })

    await act(async () => {
      result.current.deleteAttachment()
    })

    expect(result.current.invoiceAttachment).toBeNull()
  })
})
