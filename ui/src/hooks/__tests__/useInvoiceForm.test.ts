import { act, renderHook, waitFor } from '@testing-library/react'
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

  it('submits coerced numeric fields through the Zod resolver', async () => {
    const { result } = renderHook(() => useInvoiceForm({}))
    await waitFor(() => expect(result.current.loading).toBe(false))
    const submit = vi.fn()
    await act(async () => {
      result.current.form.setValue('client', '1')
      result.current.form.setValue('items', [{ description: 'Service', quantity: '2' as unknown as number, price: '12.50' as unknown as number }])
      result.current.form.setValue('taxRate', '5' as unknown as number)
      await result.current.form.handleSubmit(submit)()
    })
    expect(submit).toHaveBeenCalledOnce()
    expect(submit.mock.calls[0][0]).toMatchObject({
      items: [{ description: 'Service', quantity: 2, price: 12.5 }],
      taxRate: 5,
      discountType: 'percentage',
    })
  })

  it('rejects invalid invoice amounts through the Zod resolver', async () => {
    const { result } = renderHook(() => useInvoiceForm({}))
    await waitFor(() => expect(result.current.loading).toBe(false))
    const submit = vi.fn()
    const invalid = vi.fn()
    await act(async () => {
      result.current.form.setValue('client', '1')
      result.current.form.setValue('items', [{ description: 'Service', quantity: 0, price: -1 }])
      await result.current.form.handleSubmit(submit, invalid)()
    })
    expect(submit).not.toHaveBeenCalled()
    expect(invalid.mock.calls[0][0].items[0].quantity.message).toBe('Quantity must be greater than 0')
    expect(invalid.mock.calls[0][0].items[0].price.message).toBe('Price must be greater than 0')
  })
})
