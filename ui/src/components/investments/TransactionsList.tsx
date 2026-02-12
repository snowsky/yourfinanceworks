import React from 'react';
import { useQuery } from '@tanstack/react-query';

import { useTranslation } from 'react-i18next';
import { useLocaleFormatter } from '@/i18n/formatters';
import {
  ArrowUpRight, ArrowDownRight, DollarSign, TrendingUp,
  TrendingDown, Calendar, Hash, FileText
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { investmentApi, InvestmentTransaction } from '@/lib/api';
import { cn } from '@/lib/utils';

interface TransactionsListProps {
  portfolioId: number;
}

const TransactionsList: React.FC<TransactionsListProps> = ({ portfolioId }) => {
  const { t } = useTranslation('investments');
  const formatter = useLocaleFormatter();

  const { data: transactions, isLoading } = useQuery<InvestmentTransaction[]>({
    queryKey: ['transactions', portfolioId],
    queryFn: () => investmentApi.getTransactions(portfolioId),
    enabled: !!portfolioId,
  });

  const getTransactionTypeIcon = (type: string) => {
    switch (type) {
      case 'BUY':
      case 'DEPOSIT':
      case 'TRANSFER_IN':
        return <ArrowDownRight className="w-4 h-4 text-green-600" />;
      case 'SELL':
      case 'WITHDRAWAL':
      case 'TRANSFER_OUT':
        return <ArrowUpRight className="w-4 h-4 text-red-600" />;
      case 'DIVIDEND':
      case 'INTEREST':
        return <DollarSign className="w-4 h-4 text-blue-600" />;
      case 'FEE':
        return <TrendingDown className="w-4 h-4 text-orange-600" />;
      default:
        return <FileText className="w-4 h-4 text-gray-600" />;
    }
  };

  const getTransactionTypeBadge = (type: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
      'BUY': 'default',
      'SELL': 'destructive',
      'DIVIDEND': 'secondary',
      'INTEREST': 'secondary',
      'FEE': 'outline',
      'DEPOSIT': 'default',
      'WITHDRAWAL': 'destructive',
      'TRANSFER_IN': 'default',
      'TRANSFER_OUT': 'destructive',
    };

    return (
      <Badge variant={variants[type] || 'outline'} className="font-medium">
        {type.replace('_', ' ')}
      </Badge>
    );
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse font-medium">
          {t('Loading transactions...')}
        </p>
      </div>
    );
  }

  if (!transactions || transactions.length === 0) {
    return (
      <div className="text-center py-20 bg-muted/20 rounded-3xl border-2 border-dashed border-border/50">
        <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-20" />
        <p className="text-muted-foreground font-medium">
          {t('No transactions found')}
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          {t('Upload a portfolio statement with transaction history to see transactions here')}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="font-semibold">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                {t('Date')}
              </div>
            </TableHead>
            <TableHead className="font-semibold">{t('Type')}</TableHead>
            <TableHead className="font-semibold">{t('Security')}</TableHead>
            <TableHead className="text-right font-semibold">
              <div className="flex items-center justify-end gap-2">
                <Hash className="w-4 h-4" />
                {t('Quantity')}
              </div>
            </TableHead>
            <TableHead className="text-right font-semibold">{t('Price')}</TableHead>
            <TableHead className="text-right font-semibold">{t('Amount')}</TableHead>
            <TableHead className="text-right font-semibold">{t('Fees')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {transactions.map((transaction) => (
            <TableRow key={transaction.id} className="hover:bg-muted/30 transition-colors">
              <TableCell className="font-medium">
                {formatter.formatDate(new Date(transaction.transaction_date))}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {getTransactionTypeIcon(transaction.transaction_type)}
                  {getTransactionTypeBadge(transaction.transaction_type)}
                </div>
              </TableCell>
              <TableCell>
                {transaction.security_symbol ? (
                  <div>
                    <div className="font-medium">{transaction.security_symbol}</div>
                    {transaction.security_name && (
                      <div className="text-xs text-muted-foreground">
                        {transaction.security_name}
                      </div>
                    )}
                  </div>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-right font-mono">
                {transaction.quantity !== null && transaction.quantity !== undefined
                  ? formatter.formatNumber(transaction.quantity)
                  : '—'}
              </TableCell>
              <TableCell className="text-right font-mono">
                {transaction.price_per_share !== null && transaction.price_per_share !== undefined
                  ? formatter.formatCurrency(transaction.price_per_share)
                  : '—'}
              </TableCell>
              <TableCell
                className={cn(
                  'text-right font-mono font-semibold',
                  transaction.total_amount >= 0 ? 'text-green-600' : 'text-red-600'
                )}
              >
                {formatter.formatCurrency(Math.abs(transaction.total_amount))}
              </TableCell>
              <TableCell className="text-right font-mono text-muted-foreground">
                {transaction.fees > 0 ? formatter.formatCurrency(transaction.fees) : '—'}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

export default TransactionsList;
