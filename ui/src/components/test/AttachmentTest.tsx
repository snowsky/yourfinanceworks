import React, { useState } from 'react';
import { FileText } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

export function AttachmentTest() {
  const [testAttachment, setTestAttachment] = useState<File | null>(null);

  return (
    <div className="p-6 border rounded-lg bg-card">
      <h2 className="text-lg font-semibold mb-4">Attachment Test Component</h2>
      
      {/* Test attachment section */}
      <div className="space-y-4">
        <h3 className="text-lg font-medium">Attachment</h3>
        
        {/* Show uploaded attachment */}
        {testAttachment && (
          <div className="flex items-center gap-2 p-3 bg-muted rounded-lg border">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">{testAttachment.name}</span>
            <span className="text-xs text-muted-foreground">({(testAttachment.size / 1024 / 1024).toFixed(2)} MB)</span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setTestAttachment(null)}
            >
              Remove
            </Button>
          </div>
        )}
        
        {/* Upload new attachment */}
        {!testAttachment && (
          <div className="space-y-2">
            <Label htmlFor="test-attachment">{t('invoices.upload_attachment')}</Label>
            <Input
              id="test-attachment"
              type="file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setTestAttachment(file);
                }
              }}
              className="cursor-pointer"
            />
            <p className="text-xs text-muted-foreground">
              {t('invoices.supported_formats')}: PDF, DOC, DOCX, JPG, PNG (Max 10MB)
            </p>
          </div>
        )}
      </div>
      
      <div className="mt-4 p-3 bg-primary/10 rounded border border-primary/30">
        <p className="text-sm text-primary">
          <strong>Test Status:</strong> {testAttachment ? `File selected: ${testAttachment.name}` : 'No file selected'}
        </p>
      </div>
    </div>
  );
}