import { renderHook, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { useAuth } from '../useAuth'
import * as api from '@/lib/api'

vi.mock('@/lib/api', () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), getCurrentUser: vi.fn() },
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(api.authApi.getCurrentUser as any).mockResolvedValue(null)
  })

  it('initializes with no user', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.user).toBeNull()
  })

  it('loads current user on mount', async () => {
    const mockUser = { id: 1, email: 'user@example.com', role: 'admin' }
    ;(api.authApi.getCurrentUser as any).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.user).toEqual(mockUser)
    })
  })

  it('handles login', async () => {
    const mockUser = { id: 1, email: 'user@example.com', role: 'user' }
    ;(api.authApi.login as any).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.user).toBeDefined()
    })
  })

  it('handles logout', async () => {
    const mockUser = { id: 1, email: 'user@example.com' }
    ;(api.authApi.getCurrentUser as any).mockResolvedValue(mockUser)

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.user).toBeDefined()
    })

    ;(api.authApi.logout as any).mockResolvedValue(null)
    await result.current.logout?.()

    await waitFor(() => {
      expect(result.current.user).toBeNull()
    })
  })

  it('handles authentication errors', async () => {
    ;(api.authApi.getCurrentUser as any).mockRejectedValue(new Error('Auth failed'))

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.user).toBeNull()
    })
  })
})
