import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDate } from "@/lib/utils";
import { Invoice } from "@/lib/api";
import { Calendar, Clock, FileText, MoreVertical, Pencil, Copy, Trash2, User, DollarSign } from "lucide-react";
import { Link } from "react-router-dom";

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

const formatStatus = (status: string) => {
  return status.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ');
};

export function InvoiceCard({ invoice, onClone, onDelete, canPerformActions = true }: InvoiceCardProps) {
  const statusConfig = getStatusConfig(invoice.status);
  const outstandingBalance = invoice.amount - (invoice.paid_amount || 0);
  const isOverdue = invoice.status === 'overdue';
  const isPaid = invoice.status === 'paid';

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
              {formatStatus(invoice.status)}
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
                    <Link to={`/invoices/edit/${invoice.id}`} className="flex items-center w-full">
                      <Pencil className="mr-2 h-4 w-4" />
                      Edit
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => onClone?.(invoice.id)}>
                    <Copy className="mr-2 h-4 w-4" />
                    Clone
                  </DropdownMenuItem>
                  <DropdownMenuItem 
                    onClick={() => onDelete?.(invoice.id)}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
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
              <span className="text-muted-foreground">Created:</span>
              <span className="font-medium">{formatDate(invoice.created_at)}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Clock className={`h-4 w-4 ${isOverdue ? 'text-destructive' : 'text-muted-foreground'}`} />
              <span className="text-muted-foreground">Due:</span>
              <span className={`font-medium ${isOverdue ? 'text-destructive' : ''}`}>
                {formatDate(invoice.due_date)}
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <DollarSign className="h-4 w-4 text-success" />
              <span className="text-muted-foreground">Paid:</span>
              <span className="font-medium text-success">
                <CurrencyDisplay amount={invoice.paid_amount || 0} currency={invoice.currency} />
              </span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <DollarSign className={`h-4 w-4 ${outstandingBalance > 0 ? 'text-warning' : 'text-success'}`} />
              <span className="text-muted-foreground">Outstanding:</span>
              <span className={`font-medium ${outstandingBalance > 0 ? 'text-warning' : 'text-success'}`}>
                <CurrencyDisplay amount={outstandingBalance} currency={invoice.currency} />
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t">
          <div className="text-right">
            <div className="text-sm text-muted-foreground">Total Amount</div>
            <div className="text-2xl font-bold text-primary">
              <CurrencyDisplay amount={invoice.amount} currency={invoice.currency} />
            </div>
          </div>
          
          {canPerformActions && (
            <Button asChild variant="outline" size="sm">
              <Link to={`/invoices/edit/${invoice.id}`}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit Invoice
              </Link>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}