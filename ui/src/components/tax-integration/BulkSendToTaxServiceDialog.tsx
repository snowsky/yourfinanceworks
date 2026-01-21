import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Loader2, Send, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useTranslation } from 'react-i18next';
import { Expense, Invoice } from '@/lib/api';

interface BulkSendToTaxServiceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: (Expense | Invoice)[];
  itemType: 'expense' | 'invoice';
  onSuccess?: () => void;
}

interface BulkResult {
  item_id: number;
  success: boolean;
  transaction_id?: string;
  error_message?: string;
}

interface IntegrationStatus {
  enabled: boolean;
  configured: boolean;
  connection_tested: boolean;
  last_test_result?: string;
}

export const BulkSendToTaxServiceDialog: React.FC<BulkSendToTaxServiceDialogProps> = ({
  open,
  onOpenChange,
  items,
  itemType,
  onSuccess,
}) => {
  const { t } = useTranslation();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<BulkResult[]>([]);
  const [integrationStatus, setIntegrationStatus] = useState<IntegrationStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  useEffect(() => {
    const fetchIntegrationStatus = async () => {
      try {
        const response = await api.get<IntegrationStatus>('/tax-integration/status');
        setIntegrationStatus(response);
      } catch (error) {
        console.error('Error fetching tax integration status:', error);
        // Default to disabled if we can't fetch status
        setIntegrationStatus({
          enabled: false,
          configured: false,
          connection_tested: false,
        });
      } finally {
        setStatusLoading(false);
      }
    };

    fetchIntegrationStatus();
  }, []);

  React.useEffect(() => {
    if (open) {
      // Select all items by default when dialog opens
      setSelectedIds(items.map(item => item.id));
      setResults([]);
    }
  }, [open, items]);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(items.map(item => item.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectItem = (itemId: number, checked: boolean) => {
    if (checked) {
      setSelectedIds(prev => [...prev, itemId]);
    } else {
      setSelectedIds(prev => prev.filter(id => id !== itemId));
    }
  };

  const handleBulkSend = async () => {
    if (selectedIds.length === 0) {
      toast.error(t('taxIntegration.errors.noItemsSelected'));
      return;
    }

    if (!integrationStatus?.enabled || !integrationStatus?.configured) {
      toast.error(t('taxIntegration.errors.notEnabled'));
      return;
    }

    setIsProcessing(true);
    setResults([]);

    try {
      const response = await api.post<{
        total_items: number;
        successful: number;
        failed: number;
        results: BulkResult[];
      }>(`/tax-integration/send-bulk`, {
        item_ids: selectedIds,
        item_type: itemType,
      });

      setResults(response.results);

      if (response.successful > 0) {
        toast.success(
          t('taxIntegration.success.bulkSendCompleted', {
            successful: response.successful,
            total: response.total_items,
          })
        );
      }

      if (response.failed > 0) {
        toast.error(
          t('taxIntegration.errors.bulkSendPartialFailure', {
            failed: response.failed,
            total: response.total_items,
          })
        );
      }

      if (response.successful > 0) {
        onSuccess?.();
      }
    } catch (error: any) {
      console.error('Error in bulk send:', error);
      toast.error(
        error?.message || t('taxIntegration.errors.bulkSendFailed')
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const getItemDisplayName = (item: Expense | Invoice) => {
    if (itemType === 'expense') {
      const expense = item as Expense;
      return `${expense.vendor || t('common.unknownVendor')} - $${expense.amount}`;
    } else {
      const invoice = item as Invoice;
      return `${invoice.number} - ${invoice.client_name} - $${invoice.amount}`;
    }
  };

  const getResultIcon = (result: BulkResult) => {
    return result.success ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <XCircle className="h-4 w-4 text-red-500" />
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {t('taxIntegration.bulkSendTitle', {
              itemType: itemType === 'expense' ? t('common.expenses') : t('common.invoices'),
            })}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Development Notice */}
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
              <p className="text-sm text-amber-800">
                {t('taxIntegration.developmentNotice')}
              </p>
            </div>
          </div>
          {/* Selection Summary */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
            <div className="flex items-center space-x-2">
              <Checkbox
                checked={selectedIds.length === items.length}
                onCheckedChange={handleSelectAll}
              />
              <span className="text-sm font-medium">
                {t('taxIntegration.selectAll')}
              </span>
            </div>
            <Badge variant="secondary">
              {selectedIds.length} / {items.length} {t('common.selected')}
            </Badge>
          </div>

          {/* Items List */}
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-center space-x-3 p-3 border rounded-md hover:bg-gray-50"
              >
                <Checkbox
                  checked={selectedIds.includes(item.id)}
                  onCheckedChange={(checked) =>
                    handleSelectItem(item.id, checked as boolean)
                  }
                />
                <div className="flex-1">
                  <p className="text-sm font-medium">
                    {getItemDisplayName(item)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    ID: {item.id}
                  </p>
                </div>
                {results.find(r => r.item_id === item.id) && (
                  <div className="flex items-center space-x-1">
                    {getResultIcon(results.find(r => r.item_id === item.id)!)}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Results Summary */}
          {results.length > 0 && (
            <div className="p-3 bg-blue-50 border border-blue-200 rounded-md">
              <h4 className="text-sm font-medium text-blue-900 mb-2">
                {t('taxIntegration.results')}
              </h4>
              <div className="space-y-1">
                {results.map((result) => (
                  <div key={result.item_id} className="flex items-center space-x-2 text-sm">
                    {getResultIcon(result)}
                    <span>
                      {t('common.item')} {result.item_id}:
                      {result.success ? (
                        <span className="text-green-600 ml-1">
                          {t('common.success')} (ID: {result.transaction_id})
                        </span>
                      ) : (
                        <span className="text-red-600 ml-1">
                          {t('common.failed')}: {result.error_message}
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isProcessing}
          >
            {t('common.cancel')}
          </Button>
          <Button
            onClick={handleBulkSend}
            disabled={
              selectedIds.length === 0 ||
              isProcessing ||
              !integrationStatus?.enabled ||
              !integrationStatus?.configured
            }
          >
            {isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <Send className="h-4 w-4 mr-2" />
            )}
            {t('taxIntegration.sendSelected', { count: selectedIds.length })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
