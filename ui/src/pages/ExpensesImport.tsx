import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { expenseApi, Expense } from '@/lib/api';
import { useNavigate } from 'react-router-dom';

type ImportItem = {
  file: File;
  status: 'pending' | 'creating' | 'uploading' | 'queued' | 'error' | 'done';
  error?: string;
  expense?: Expense;
};

export default function ExpensesImport() {
  const navigate = useNavigate();
  const [items, setItems] = useState<ImportItem[]>([]);
  const [processing, setProcessing] = useState(false);

  const canStart = useMemo(() => items.length > 0 && !processing, [items.length, processing]);

  const onFilesSelected = (files: FileList | null) => {
    if (!files) return;
    const selected = Array.from(files).slice(0, 10);
    const mapped: ImportItem[] = selected.map((f) => ({ file: f, status: 'pending' }));
    setItems(mapped);
  };

  const startImport = async () => {
    if (items.length === 0) return;
    setProcessing(true);

    const addNotification = (window as any).addAINotification;
    addNotification?.('processing', 'Processing Expense Files', `Analyzing ${items.length} expense files with AI...`);

    const next: ImportItem[] = [...items];
    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < next.length; i++) {
      try {
        next[i].status = 'creating';
        setItems([...next]);
        // Create base expense with amount 0, category General; mark imported and queued
        const base = {
          amount: 0,
          currency: 'USD',
          expense_date: new Date().toISOString().split('T')[0],
          category: 'General',
          status: 'recorded',
          notes: `Imported from file: ${next[i].file.name}`,
          imported_from_attachment: true,
          analysis_status: 'queued',
        } as any;
        const created = await expenseApi.createExpense(base);
        next[i].status = 'uploading';
        next[i].expense = created;
        setItems([...next]);
        await expenseApi.uploadReceipt(created.id, next[i].file);
        // After upload, it will be queued/processed by backend
        next[i].status = 'queued';
        setItems([...next]);
        (window as any).startExpensePolling?.(created.id);
        successCount++;
      } catch (e: any) {
        next[i].status = 'error';
        next[i].error = e?.message || 'Failed to import';
        setItems([...next]);
        errorCount++;
      }
    }

    setProcessing(false);

    // Add completion notification based on upload success only
    if (errorCount === 0) {
      addNotification?.('success', 'Expense Files Uploaded', `Successfully uploaded ${successCount} expense files. AI analysis in progress.`);
      navigate('/expenses');
    } else if (successCount > 0) {
      addNotification?.('error', 'Expense Upload Partial', `Uploaded ${successCount} files successfully, ${errorCount} failed.`);
    } else {
      addNotification?.('error', 'Expense Upload Failed', `Failed to upload all ${errorCount} expense files.`);
    }

    toast.success('Import completed');
  };

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Import Expenses</h1>
            <p className="text-muted-foreground">Select up to 10 PDF or image files to create expenses. Each file becomes a separate expense and will be analyzed by OCR.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate('/expenses')}>Back to Expenses</Button>
            <Button onClick={startImport} disabled={!canStart}>{processing ? 'Importing...' : 'Start Import'}</Button>
          </div>
        </div>

        <Card className="slide-in">
          <CardHeader>
            <CardTitle>Select Files</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <input
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                multiple
                onChange={(e) => onFilesSelected(e.target.files)}
              />
              <div className="text-xs text-muted-foreground mt-2">Up to 10 files. Supported types: PDF, JPG, PNG.</div>
            </div>

            <div className="space-y-2">
              {items.length === 0 ? (
                <div className="text-sm text-muted-foreground">No files selected.</div>
              ) : (
                <ul className="space-y-2">
                  {items.map((it, idx) => (
                    <li key={idx} className="flex items-center justify-between border rounded p-2">
                      <div className="truncate text-sm">
                        {it.file.name}
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        {it.status === 'pending' && <span className="text-muted-foreground">Pending</span>}
                        {it.status === 'creating' && <span className="text-amber-700 bg-amber-100 px-2 py-0.5 rounded">Creating</span>}
                        {it.status === 'uploading' && <span className="text-blue-700 bg-blue-100 px-2 py-0.5 rounded">Uploading</span>}
                        {it.status === 'queued' && <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded">Queued</span>}
                        {it.status === 'done' && <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded">Done</span>}
                        {it.status === 'error' && <span className="text-red-700 bg-red-100 px-2 py-0.5 rounded">Error: {it.error}</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
