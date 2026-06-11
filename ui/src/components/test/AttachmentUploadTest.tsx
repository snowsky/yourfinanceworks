import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { invoiceApi } from '@/lib/api';
import { toast } from 'sonner';

export function AttachmentUploadTest() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [invoiceId, setInvoiceId] = useState<string>('');

  const handleUpload = async () => {
    if (!file || !invoiceId) {
      toast.error('Please select a file and enter an invoice ID');
      return;
    }

    setUploading(true);
    try {
      console.log('Uploading file:', file.name, 'to invoice:', invoiceId);
      const result = await invoiceApi.uploadAttachment(parseInt(invoiceId), file);
      console.log('Upload result:', result);
      
      // Fetch updated invoice to verify attachment was saved
      const updatedInvoice = await invoiceApi.getInvoice(parseInt(invoiceId));
      console.log('Updated invoice:', updatedInvoice);
      console.log('Has attachment:', updatedInvoice.has_attachment);
      console.log('Attachment filename:', updatedInvoice.attachment_filename);
      
      toast.success('Attachment uploaded successfully!');
      setFile(null);
    } catch (error) {
      console.error('Upload failed:', error);
      toast.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-4 border rounded-lg space-y-4">
      <h3 className="text-lg font-semibold">Attachment Upload Test</h3>
      
      <div>
        <label>Invoice ID:</label>
        <Input
          type="number"
          value={invoiceId}
          onChange={(e) => setInvoiceId(e.target.value)}
          placeholder="Enter invoice ID"
        />
      </div>
      
      <div>
        <label>File:</label>
        <Input
          type="file"
          accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </div>
      
      {file && (
        <div className="text-sm text-muted-foreground">
          Selected: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
        </div>
      )}
      
      <Button 
        onClick={handleUpload} 
        disabled={!file || !invoiceId || uploading}
      >
        {uploading ? 'Uploading...' : 'Upload Attachment'}
      </Button>
    </div>
  );
}