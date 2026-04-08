import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';

interface StatusBadgeProps {
  status?: string;
  extraction_method?: string | null;
  analysis_error?: string | null;
}

export function StatusBadge({ status, extraction_method, analysis_error }: StatusBadgeProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-1">
      <Badge
        variant="outline"
        className={`
          font-medium capitalize h-6 px-3
          ${status === 'processed' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800' : ''}
          ${status === 'processing' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-blue-200 dark:border-blue-800 animate-pulse' : ''}
          ${status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800' : ''}
          ${status === 'uploaded' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800' : ''}
          ${status === 'merged' ? 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300 border-violet-200 dark:border-violet-800' : ''}
        `}
      >
        {status === 'merged' ? t('common.merged', 'Merged') : (status === 'processed' || status === 'done') ? t('common.done', 'Done') : t(`common.${status || 'unknown'}`, status || 'Unknown')}
      </Badge>
      {status === 'processed' && extraction_method && (
        <span className="text-[10px] text-muted-foreground ml-1 uppercase font-bold tracking-tighter">
          via {extraction_method}
        </span>
      )}
      {status === 'failed' && analysis_error && (
        <span className="text-[10px] text-red-600 dark:text-red-400 ml-1 line-clamp-2" title={analysis_error}>
          {analysis_error}
        </span>
      )}
    </div>
  );
}
