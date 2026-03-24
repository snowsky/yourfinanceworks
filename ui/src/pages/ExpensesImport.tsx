import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { expenseApi, Expense } from '@/lib/api';
import { useNavigate } from 'react-router-dom';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { Upload, FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type ImportItem = {
  file: File;
  status: 'pending' | 'creating' | 'uploading' | 'done' | 'error';
  error?: string;
  expense?: Expense;
};

export default function ExpensesImport() {
  const { t } = useTranslation();
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
        next[i].status = 'done';
        setItems([...next]);
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
      addNotification?.('success', t('expenses.import_notifications.files_uploaded'), t('expenses.import_notifications.files_uploaded_success', { count: successCount }));
      navigate('/expenses');
    } else if (successCount > 0) {
      addNotification?.('error', t('expenses.import_notifications.upload_partial'), t('expenses.import_notifications.upload_partial_message', { success: successCount, failed: errorCount }));
    } else {
      addNotification?.('error', t('expenses.import_notifications.upload_failed'), t('expenses.import_notifications.upload_failed_message', { failed: errorCount }));
    }

    toast.success(t('expenses.import_completed'));
  };

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight">{t('expenses.page.title')}</h1>
              <p className="text-lg text-muted-foreground">{t('expenses.page.description')}</p>
            </div>
            <div className="flex gap-4">
              <Button variant="outline" onClick={() => navigate('/expenses')} className="h-10">{t('expenses.page.back_to_expenses')}</Button>
              <Button onClick={startImport} disabled={!canStart} className="h-10">{processing ? t('expenses.page.importing') : t('expenses.page.start_import')}</Button>
            </div>
          </div>
        </div>

        <ProfessionalCard className="slide-in" variant="elevated">
          <div className="space-y-6">
            <div className="pb-6 border-b border-border/50">
              <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
                <Upload className="h-5 w-5" />
                {t('expenses.page.select_files')}
              </h2>
              <p className="text-muted-foreground mt-1">{t('expenses.page.select_files_description')}</p>
            </div>
            <div className="space-y-4">
              <div className="border-2 border-dashed border-border/50 rounded-lg p-8 hover:border-primary/50 transition-colors">
                <div className="flex flex-col items-center justify-center gap-4">
                  <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center">
                    <FileText className="h-8 w-8 text-primary" />
                  </div>
                  <div className="text-center">
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <span className="text-primary font-semibold hover:underline">{t('expenses.page.click_to_upload')}</span>
                      <span className="text-muted-foreground"> {t('expenses.page.drag_and_drop')}</span>
                    </label>
                    <p className="text-xs text-muted-foreground mt-2">{t('expenses.page.file_types_supported')}</p>
                  </div>
                  <input
                    id="file-upload"
                    type="file"
                    accept="application/pdf,image/jpeg,image/png"
                    multiple
                    onChange={(e) => onFilesSelected(e.target.files)}
                    className="hidden"
                  />
                </div>
              </div>

              <div className="space-y-3">
                {items.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <p className="text-sm">{t('expenses.page.no_files_selected')}</p>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between pb-2">
                      <h3 className="text-sm font-semibold text-foreground">{t('expenses.page.selected_files', { count: items.length })}</h3>
                    </div>
                    <ul className="space-y-2">
                      {items.map((it, idx) => (
                        <li key={idx} className="flex items-center justify-between border border-border/50 rounded-lg p-4 bg-muted/20 hover:bg-muted/40 transition-colors">
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className="bg-primary/10 p-2 rounded-lg">
                              <FileText className="h-4 w-4 text-primary" />
                            </div>
                            <div className="truncate text-sm font-medium text-foreground">
                              {it.file.name}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 text-xs ml-4">
                            {it.status === 'pending' && <span className="px-3 py-1 rounded-full bg-muted text-muted-foreground font-medium">{t('expenses.page.status.pending')}</span>}
                            {it.status === 'creating' && <span className="px-3 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 font-medium">{t('expenses.page.status.creating')}</span>}
                            {it.status === 'uploading' && <span className="px-3 py-1 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 font-medium">{t('expenses.page.status.uploading')}</span>}
                            {it.status === 'done' && <span className="px-3 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 font-medium">{t('expenses.page.status.uploaded')}</span>}
                            {it.status === 'error' && <span className="px-3 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 font-medium">{t('expenses.page.status.error')}: {it.error}</span>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>
          </div>
        </ProfessionalCard>
      </div>
    </>
  );
}
