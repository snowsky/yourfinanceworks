import { renderHook, waitFor, act } from '@testing-library/react'
import { vi } from 'vitest'
import { useNotifications } from '../useNotifications'

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))

describe('useNotifications', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes with empty notifications', () => {
    const { result } = renderHook(() => useNotifications())
    expect(result.current.notifications).toEqual([])
  })

  it('adds notification', async () => {
    const { result } = renderHook(() => useNotifications())

    await act(async () => {
      result.current.addNotification('Test message', 'info')
    })

    await waitFor(() => {
      expect(result.current.notifications.length).toBeGreaterThan(0)
    })
  })

  it('removes notification', async () => {
    const { result } = renderHook(() => useNotifications())

    await act(async () => {
      result.current.addNotification('Test', 'info')
    })

    const notificationId = result.current.notifications[0]?.id

    await act(async () => {
      result.current.removeNotification(notificationId)
    })

    await waitFor(() => {
      expect(result.current.notifications).toEqual([])
    })
  })

  it('clears all notifications', async () => {
    const { result } = renderHook(() => useNotifications())

    await act(async () => {
      result.current.addNotification('Test 1', 'info')
      result.current.addNotification('Test 2', 'error')
    })

    await act(async () => {
      result.current.clearNotifications()
    })

    expect(result.current.notifications).toEqual([])
  })
})
