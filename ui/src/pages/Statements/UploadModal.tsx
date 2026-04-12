import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Upload, X, FileText } from 'lucide-react';
import { STATEMENT_PROVIDERS } from './types';

interface UploadModalProps {
  open: boolean;
  onClose: () => void;
  files: File[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
  selectedProvider: string;
  setSelectedProvider: (v: string) => void;
  cardType: string;
  setCardType: (v: string) => void;
  dragActive: boolean;
  setDragActive: (v: boolean) => void;
  loading: boolean;
  onUpload: () => void;
}

export function UploadModal({
  open,
  onClose,
  files,
  onAddFiles,
  onRemoveFile,
  selectedProvider,
  setSelectedProvider,
  cardType,
  setCardType,
  dragActive,
  setDragActive,
  loading,
  onUpload,
}: UploadModalProps) {
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose(); }}>
      <DialogContent
        className="sm:max-w-md flex flex-col max-h-[80vh]"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{t('statements.upload_statement', { defaultValue: 'Upload Statement' })}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 overflow-y-auto flex-1 px-1">
          <div>
            <label className="text-sm font-medium mb-2 block">
              {t('statements.select_provider', { defaultValue: 'Statement Provider' })}
            </label>
            <Select value={selectedProvider} onValueChange={setSelectedProvider}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATEMENT_PROVIDERS.map((provider) => (
                  <SelectItem key={provider.value} value={provider.value}>
                    <div className="flex items-center gap-2">
                      <span>{provider.icon}</span>
                      <span>{provider.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">
              {t('statements.card_type.label', 'Card Type')}
            </label>
            <Select value={cardType} onValueChange={setCardType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">Auto-detect (AI)</SelectItem>
                <SelectItem value="debit">Debit Card (Standard)</SelectItem>
                <SelectItem value="credit">Credit Card (Inverted)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-sm font-medium mb-2 block">
              {t('statements.select_files')}
            </label>
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-6 text-center transition-colors",
                dragActive ? "border-primary bg-primary/10" : "border-muted-foreground/25"
              )}
              onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(true); }}
              onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false); }}
              onDrop={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setDragActive(false);
                if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                  onAddFiles(Array.from(e.dataTransfer.files));
                }
              }}
            >
              <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
              <div className="text-sm text-muted-foreground mb-2">
                {files.length > 0 ? `${files.length} file(s) selected` : t('statements.drop_files_here')}
              </div>
              <div className="relative inline-flex">
                <span className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium pointer-events-none">
                  <Upload className="w-4 h-4 mr-2" />
                  {t('statements.choose_files')}
                </span>
                <input
                  type="file"
                  accept=".pdf,.csv,.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp,application/pdf,text/csv,application/vnd.ms-excel"
                  multiple
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  onChange={(e) => {
                    onAddFiles(Array.from(e.target.files || []));
                    e.target.value = '';
                  }}
                />
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                {t('statements.supported_formats')}
              </div>
            </div>
            {files.length > 0 && (
              <div className="mt-4">
                <div className="text-sm font-medium mb-2">Selected Files:</div>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {files.map((file, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-md group border border-transparent hover:border-border/50 transition-all overflow-hidden">
                      <FileText className="w-4 h-4 text-primary/60 shrink-0" />
                      <span className="truncate font-medium min-w-0 flex-1">{file.name}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0 opacity-70">({Math.round(file.size / 1024)} KB)</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0"
                        onClick={() => onRemoveFile(index)}
                      >
                        <X className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-4 border-t border-border/50 shrink-0">
          <Button variant="outline" onClick={onClose}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button onClick={onUpload} disabled={loading || files.length === 0}>
            {loading ? (
              <>
                <div className="w-4 h-4 mr-2 border-2 border-current border-t-transparent rounded-full animate-spin" />
                {t('statements.processing')}
              </>
            ) : (
              <>
                <Upload className="w-4 h-4 mr-2" />
                {t('statements.upload')}
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
