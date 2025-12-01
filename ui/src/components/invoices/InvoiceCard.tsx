import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDate } from "@/lib/utils";
import { Invoice, api } from "@/lib/api";
import { Calendar, Clock, FileText, MoreVertical, Pencil, Copy, Trash2, User, DollarSign, Send, Eye } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { useTaxIntegration } from "@/hooks/useTaxIntegration";

interface InvoiceCardProps {
  invoice: Invoice;
  onClone?: (id: number) => void;
  onDelete?: (id: number) => void;
  canPerformActions?: boolean;
}

const getStatusConfig = (status: string) => {
  switch (status) {
    case 'paid':
      return {
        variant: 'default' as const,
        className: 'status-paid',
        icon: '✓'
      };
    case 'pending':
      return {
        variant: 'secondary' as const,
        className: 'status-pending',
        icon: '⏳'
      };
    case 'overdue':
      return {
        variant: 'destructive' as const,
        className: 'status-overdue',
        icon: '⚠️'
      };
    case 'partially_paid':
      return {
        variant: 'outline' as const,
        className: 'status-partially-paid',
        icon: '◐'
      };
    default:
      return {
        variant: 'outline' as const,
        className: 'bg-muted/50 text-muted-foreground',
        icon: '📄'
      };
  }
};


export function InvoiceCard({ invoice, onClone, onDelete, canPerformActions = true }: InvoiceCardProps) {
  const { t } = useTranslation();
  const statusConfig = getStatusConfig(invoice.status);
  const outstandingBalance = invoice.amount - (invoice.paid_amount || 0);
  const isOverdue = invoice.status === 'overdue';
  const isPaid = invoice.status === 'paid';

  const { isEnabled: taxIntegrationEnabled } = useTaxIntegration();

  return (
    <Card className="group hover:shadow-md transition-all duration-200 border-l-4 border-l-primary/20 hover:border-l-primary">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">{invoice.number}</h3>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <User className="h-3 w-3" />
                <span>{invoice.client_name}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge className={`${statusConfig.className} font-medium`}>
              <span className="mr-1">{statusConfig.icon}</span>
              {t(`invoices.status.${invoice.status}`)}
            </Badge>

            {canPerformActions && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100 transition-opacity">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem asChild>
                    <Link to={`/invoices/view/${invoice.id}`} className="flex items-center w-full">
                      <Eye className="mr-2 h-4 w-4" />
                      {t('invoices.view_invoice')}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to={`/invoices/edit/${invoice.id}`} className="flex items-center w-full">
                      <Pencil className="mr-2 h-4 w-4" />
                      {t('invoices.edit_invoice')}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onClone?.(invoice.id)}>
                    <Copy className="mr-2 h-4 w-4" />
                    {t('invoices.clone_invoice')}
                  </DropdownMenuItem>
                  {taxIntegrationEnabled && (
                    <DropdownMenuItem onClick={async () => {
                      // Handle send to tax service directly here
                      try {
                        const response = await api.post<{
                          success: boolean;
                          transaction_id?: string;
                          error_message?: string;
                        }>('/tax-integration/send', {
                          item_id: invoice.id,
                          item_type: 'invoice',
                        });

                        if (response.success) {
                          toast.success(
                            t('taxIntegration.tax_send_success')
                          );
                        } else {
                          toast.error(
                            response.error_message || t('taxIntegration.tax_send_error')
                          );
                        }
                      } catch (error: any) {
                        console.error('Error sending to tax service:', error);
                        toast.error(
                          error?.message || t('taxIntegration.tax_send_error')
                        );
                      }
                    }}>
                      <Send className="mr-2 h-4 w-4" />
                      {t('taxIntegration.sendToTaxService')}
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem
                    onClick={() => onDelete?.(invoice.id)}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {t('invoices.delete_invoice')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">{t('invoices.created_label')}:</span>
              <span className="font-medium">{formatDate(invoice.created_at)}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Clock className={`h-4 w-4 ${isOverdue ? 'text-destructive' : 'text-muted-foreground'}`} />
              <span className="text-muted-foreground">{t('invoices.due_label')}:</span>
              <span className={`font-medium ${isOverdue ? 'text-destructive' : ''}`}>
                {formatDate(invoice.due_date)}
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <DollarSign className="h-4 w-4 text-success" />
              <span className="text-muted-foreground">{t('invoices.paid_label')}:</span>
              <span className="font-medium text-success">
                <CurrencyDisplay amount={invoice.paid_amount || 0} currency={invoice.currency} />
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <DollarSign className={`h-4 w-4 ${outstandingBalance > 0 ? 'text-warning' : 'text-success'}`} />
              <span className="text-muted-foreground">{t('invoices.outstanding_label')}:</span>
              <span className={`font-medium ${outstandingBalance > 0 ? 'text-warning' : 'text-success'}`}>
                <CurrencyDisplay amount={outstandingBalance} currency={invoice.currency} />
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t">
          <div className="text-right">
            <div className="text-sm text-muted-foreground">{t('invoices.total_amount')}</div>
            <div className="text-2xl font-bold text-primary">
              <CurrencyDisplay amount={invoice.amount} currency={invoice.currency} />
            </div>
          </div>

          {canPerformActions && (
            <Button asChild variant="outline" size="sm">
              <Link to={invoice.status === 'pending_approval' ? `/invoices/view/${invoice.id}` : `/invoices/edit/${invoice.id}`}>
                <Pencil className="mr-2 h-4 w-4" />
                {invoice.status === 'pending_approval' ? t('invoices.view_invoice') : t('invoices.edit_invoice')}
              </Link>
            </Button>
          )}
        </div>
      </CardContent>

    </Card>
  );
}