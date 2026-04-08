import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { CreditCard, Wallet } from 'lucide-react';

interface CardTypeBadgeProps {
  type?: string;
}

export function CardTypeBadge({ type }: CardTypeBadgeProps) {
  const { t } = useTranslation();
  const isCredit = type === 'credit';
  const isAuto = !type || type === 'auto';

  if (isAuto) {
    return (
      <Badge
        variant="secondary"
        className="flex items-center gap-1.5 h-6 px-2.5 font-medium border shadow-sm bg-gray-100 text-gray-600 dark:bg-gray-800/40 dark:text-gray-400 border-gray-200 dark:border-gray-700"
      >
        <Wallet className="h-3.5 w-3.5" />
        {t('statements.card_type.auto', 'Auto')}
      </Badge>
    );
  }

  return (
    <Badge
      variant="secondary"
      className={cn(
        "flex items-center gap-1.5 h-6 px-2.5 font-medium border shadow-sm",
        isCredit
          ? "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border-purple-200 dark:border-purple-800"
          : "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-blue-200 dark:border-blue-800"
      )}
    >
      {isCredit ? <CreditCard className="h-3.5 w-3.5" /> : <Wallet className="h-3.5 w-3.5" />}
      {isCredit ? t('statements.card_type.credit', 'Credit') : t('statements.card_type.debit', 'Debit')}
    </Badge>
  );
}
