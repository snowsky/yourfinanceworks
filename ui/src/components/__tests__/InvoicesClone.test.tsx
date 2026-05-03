import React from 'react'
import { describe, it, beforeEach, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'
import Invoices from '@/pages/Invoices'

vi.mock('@/utils/auth', () => ({ canPerformActions: () => true }))

const mockGetInvoices = vi.fn()
const mockCloneInvoice = vi.fn()
const mockUpdateInvoice = vi.fn()

vi.mock('@/lib/api', async (orig) => {
  const actual = await (orig() as Promise<any>)
  return {
    ...actual,
    invoiceApi: {
      ...actual.invoiceApi,
      getInvoices: (...args: any[]) => mockGetInvoices(...args),
      cloneInvoice: (...args: any[]) => mockCloneInvoice(...args),
      updateInvoice: (...args: any[]) => mockUpdateInvoice(...args),
    },
  }
})

// Mock i18n to avoid needing a full provider
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k })
}))

// Capture navigation calls
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (orig) => {
  const actual = await (orig() as Promise<any>)
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('Invoices clone action', () => {
  beforeEach(() => {
    mockGetInvoices.mockReset()
    mockCloneInvoice.mockReset()
    mockUpdateInvoice.mockReset()
    mockNavigate.mockReset()
  })

  it('shows Clone button and clones an invoice, then navigates to edit page', async () => {
    mockGetInvoices.mockResolvedValueOnce([
      { id: 10, number: 'INV-0010', client_id: 1, client_name: 'Acme Co', created_at: new Date().toISOString(), due_date: new Date().toISOString(), amount: 100, currency: 'USD', paid_amount: 0, status: 'draft', notes: '', items: [], updated_at: new Date().toISOString(), is_recurring: false },
    ])
    mockCloneInvoice.mockResolvedValueOnce({ id: 99, number: 'INV-0099', created_at: '2026-05-02T23:39:47Z' })
    mockUpdateInvoice.mockResolvedValueOnce({})

    render(<Invoices />)

    // Wait for invoice to render
    await waitFor(() => expect(screen.getByText('INV-0010')).toBeInTheDocument())

    // Click clone button (uses title attribute "Clone invoice")
    const cloneBtn = screen.getAllByTitle('Clone invoice')[0]
    fireEvent.click(cloneBtn)

    await waitFor(() => {
      expect(mockCloneInvoice).toHaveBeenCalledWith(10)
      expect(mockUpdateInvoice).toHaveBeenCalledWith(99, { due_date: '2026-06-02' })
      expect(mockNavigate).toHaveBeenCalledWith('/invoices/edit/99')
    })
  })
})
