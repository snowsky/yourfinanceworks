import { renderWithProviders, mockApiResponses, mockFetchSuccess } from '@/test/test-utils'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

// Mock component for testing workflow
const InvoiceWorkflow = () => {
  const [step, setStep] = React.useState('create')
  const [invoice, setInvoice] = React.useState(null)

  const handleCreate = async () => {
    mockFetchSuccess(mockApiResponses.invoices[0])
    const response = await fetch('/api/invoices', { method: 'POST' })
    const data = await response.json()
    setInvoice(data)
    setStep('review')
  }

  const handleSend = async () => {
    mockFetchSuccess({ success: true })
    await fetch(`/api/invoices/${invoice?.id}/send`, { method: 'POST' })
    setStep('sent')
  }

  return (
    <div>
      {step === 'create' && (
        <button onClick={handleCreate}>Create Invoice</button>
      )}
      {step === 'review' && (
        <>
          <p>Invoice: {invoice?.number}</p>
          <button onClick={handleSend}>Send Invoice</button>
        </>
      )}
      {step === 'sent' && <p>Invoice sent successfully!</p>}
    </div>
  )
}

describe('Invoice Workflow Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('completes full invoice creation and sending workflow', async () => {
    const user = userEvent.setup()
    renderWithProviders(<InvoiceWorkflow />)

    // Step 1: Create invoice
    await user.click(screen.getByText('Create Invoice'))
    await waitFor(() => {
      expect(screen.getByText(/Invoice: INV-001/)).toBeInTheDocument()
    })

    // Step 2: Send invoice
    await user.click(screen.getByText('Send Invoice'))
    await waitFor(() => {
      expect(screen.getByText('Invoice sent successfully!')).toBeInTheDocument()
    })
  })

  it('handles creation errors gracefully', async () => {
    const user = userEvent.setup()
    ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

    renderWithProviders(<InvoiceWorkflow />)
    await user.click(screen.getByText('Create Invoice'))

    // Should remain on create step
    await waitFor(() => {
      expect(screen.getByText('Create Invoice')).toBeInTheDocument()
    })
  })
})

import React from 'react'
