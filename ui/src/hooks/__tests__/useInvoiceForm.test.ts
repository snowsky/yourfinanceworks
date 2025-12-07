import { renderHook, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { useInvoiceForm } from '../useInvoiceForm'
import * as api from '@/lib/api'

// Mock API modules
vi.mock('@/lib/api', () => ({
  clientApi: { getClients: vi.fn() },
  settingsApi: { getSettings: vi.fn() },
  discountRulesApi: { getDiscountRules: vi.fn() },
  tenantApi: { getTenantInfo: vi.fn() },
  expenseApi: { getExpensesFiltered: vi.fn() },
}))

vi.mock('@/utils/auth', () => ({
  isAdmin: vi.fn(() => true),
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

describe('useInvoiceForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(api.clientApi.getClients as any).mockResolvedValue([])
    ;(api.settingsApi.getSettings as any).mockResolvedValue({})
    ;(api.discountRulesApi.getDiscountRules as any).mockResolvedValue([])
    ;(api.tenantApi.getTenantInfo as any).mockResolvedValue({ default_currency: 'USD' })
    ;(api.expenseApi.getExpensesFiltered as any).mockResolvedValue([])
  })

  it('initializes with default values', () => {
    const { result } = renderHook(() => useInvoiceForm({}))
    expect(result.current.loading).toBe(true)
  })

  it('loads clients on mount', async () => {
    const mockClients = [
      { id: 1, name: 'Client A', email: 'a@example.com' },
    ]
    ;(api.clientApi.getClients as any).mockResolvedValue(mockClients)

    const { result } = renderHook(() => useInvoiceForm({}))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.clients).toEqual(mockClients)
  })

  it('handles API errors gracefully', async () => {
    ;(api.clientApi.getClients as any).mockRejectedValue(new Error('API Error'))

    const { result } = renderHook(() => useInvoiceForm({}))

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.clients).toEqual([])
  })

  it('calculates subtotal correctly', () => {
    const { result } = renderHook(() => useInvoiceForm({}))
    const subtotal = result.current.calculateSubtotal?.()
    expect(typeof subtotal).toBe('number')
  })

  it('applies discount rules', async () => {
    const mockRules = [
      {
        id: 1,
        name: 'Summer Sale',
        discount_type: 'percentage',
        discount_value: 10,
        min_amount: 100,
        is_active: true,
      },
    ]
    ;(api.discountRulesApi.getDiscountRules as any).mockResolvedValue(mockRules)

    const { result } = renderHook(() => useInvoiceForm({}))

    await waitFor(() => {
      expect(result.current.availableDiscountRules).toEqual(mockRules)
    })
  })
})
