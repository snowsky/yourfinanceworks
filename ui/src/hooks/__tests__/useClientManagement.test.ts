import { renderHook, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { useClientManagement } from '../useClientManagement'
import * as api from '@/lib/api'

vi.mock('@/lib/api', () => ({
  clientApi: { getClients: vi.fn(), createClient: vi.fn(), updateClient: vi.fn(), deleteClient: vi.fn() },
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

describe('useClientManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(api.clientApi.getClients as any).mockResolvedValue([])
  })

  it('initializes with empty clients', () => {
    const { result } = renderHook(() => useClientManagement())
    expect(result.current.clients).toEqual([])
  })

  it('loads clients on mount', async () => {
    const mockClients = [
      { id: 1, name: 'Client A', email: 'a@example.com' },
    ]
    ;(api.clientApi.getClients as any).mockResolvedValue(mockClients)

    const { result } = renderHook(() => useClientManagement())

    await waitFor(() => {
      expect(result.current.clients).toEqual(mockClients)
    })
  })

  it('creates new client', async () => {
    const newClient = { id: 1, name: 'New Client', email: 'new@example.com' }
    ;(api.clientApi.createClient as any).mockResolvedValue(newClient)

    const { result } = renderHook(() => useClientManagement())

    await waitFor(() => {
      expect(result.current.clients).toContainEqual(newClient)
    })
  })

  it('handles client creation errors', async () => {
    ;(api.clientApi.createClient as any).mockRejectedValue(new Error('Creation failed'))

    const { result } = renderHook(() => useClientManagement())

    await waitFor(() => {
      expect(result.current.clients).toEqual([])
    })
  })
})
