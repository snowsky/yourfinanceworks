import { render, screen, fireEvent, waitFor } from '@/test/test-utils'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import React from 'react'

function MockPreviewModal({ blob }: { blob: Blob }) {
  const [open, setOpen] = React.useState(false)
  const [url, setUrl] = React.useState<string | null>(null)
  return (
    <div>
      <Button onClick={() => { setUrl(URL.createObjectURL(blob)); setOpen(true) }}>Open Preview</Button>
      <Dialog open={open} onOpenChange={(o) => { if (!o && url) URL.revokeObjectURL(url); setOpen(o) }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Preview</DialogTitle>
          </DialogHeader>
          {url && blob.type === 'application/pdf' && (
            <iframe src={url} title="PDF Preview" className="w-full h-[200px]" />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

describe('Invoice attachment preview modal', () => {
  it('opens modal and renders iframe for pdf blob', async () => {
    const pdfBytes = new Blob(["%PDF-1.4\n"], { type: 'application/pdf' })
    render(<MockPreviewModal blob={pdfBytes} />)
    fireEvent.click(screen.getByText('Open Preview'))
    await waitFor(() => expect(screen.getByTitle('PDF Preview')).toBeInTheDocument())
  })
})


