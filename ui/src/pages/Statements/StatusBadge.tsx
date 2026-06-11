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
          ${status === 'processed' ? 'bg-success/10 text-success border-success/30' : ''}
          ${status === 'processing' ? 'bg-primary/10 text-primary border-primary/30 animate-pulse' : ''}
          ${status === 'failed' ? 'bg-destructive/10 text-destructive border-destructive/30' : ''}
          ${status === 'uploaded' ? 'bg-warning/10 text-warning border-warning/30' : ''}
          ${status === 'merged' ? 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300 border-violet-200 dark:border-violet-800' : ''}
        `}
      >
        {status === 'merged' ? t('common.merged') : (status === 'processed' || status === 'done') ? t('common.done') : t(`common.${status || 'unknown'}`, status || 'Unknown')}
      </Badge>
      {status === 'processed' && extraction_method && (
        <span className="text-[10px] text-muted-foreground ml-1 uppercase font-bold tracking-tighter">
          via {extraction_method}
        </span>
      )}
      {status === 'failed' && analysis_error && (
        <span className="text-[10px] text-destructive ml-1 line-clamp-2" title={analysis_error}>
          {analysis_error}
        </span>
      )}
    </div>
  );
}
