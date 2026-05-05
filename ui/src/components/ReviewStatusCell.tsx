import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Eye,
  FileSearch,
  Loader2,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  X,
  XCircle,
} from 'lucide-react';
import type React from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn, formatDate } from '@/lib/utils';

export type ReviewStatus =
  | 'not_started'
  | 'pending'
  | 'diff_found'
  | 'no_diff'
  | 'reviewed'
  | 'failed'
  | 'rejected';

interface ReviewStatusCellProps {
  status?: ReviewStatus | null;
  reviewedAt?: string | null;
  hasReport?: boolean;
  onView?: () => void;
  onRun?: () => void;
  onCancel?: () => void;
  labels?: Partial<Record<'view' | 'run' | 'cancel' | 'clear', string>>;
  className?: string;
}

const statusConfig: Record<ReviewStatus | 'unknown', {
  label: string;
  description: string;
  icon: typeof ShieldCheck;
  badgeClass: string;
}> = {
  diff_found: {
    label: 'Needs review',
    description: 'Reviewer found differences',
    icon: AlertCircle,
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-800',
  },
  reviewed: {
    label: 'Accepted',
    description: 'Reviewer changes accepted',
    icon: CheckCircle2,
    badgeClass: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950/30 dark:text-green-300 dark:border-green-800',
  },
  no_diff: {
    label: 'Verified',
    description: 'No differences found',
    icon: ShieldCheck,
    badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-800',
  },
  pending: {
    label: 'In review',
    description: 'Review is queued or running',
    icon: Clock3,
    badgeClass: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-800',
  },
  failed: {
    label: 'Failed',
    description: 'Review could not complete',
    icon: XCircle,
    badgeClass: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-300 dark:border-red-800',
  },
  rejected: {
    label: 'Dismissed',
    description: 'Review result dismissed',
    icon: XCircle,
    badgeClass: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/50 dark:text-slate-300 dark:border-slate-700',
  },
  not_started: {
    label: 'Not started',
    description: 'No review has been run',
    icon: FileSearch,
    badgeClass: 'bg-muted/50 text-muted-foreground border-transparent',
  },
  unknown: {
    label: 'Not started',
    description: 'No review has been run',
    icon: FileSearch,
    badgeClass: 'bg-muted/50 text-muted-foreground border-transparent',
  },
};

function IconButton({
  label,
  children,
  className,
  onClick,
  disabled,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className={cn('h-7 w-7', className)}
          onClick={onClick}
          disabled={disabled}
          aria-label={label}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function ReviewStatusCell({
  status,
  reviewedAt,
  hasReport,
  onView,
  onRun,
  onCancel,
  labels,
  className,
}: ReviewStatusCellProps) {
  const normalizedStatus = status || 'not_started';
  const config = statusConfig[normalizedStatus] || statusConfig.unknown;
  const StatusIcon = config.icon;
  const canView = Boolean(onView) && (hasReport || normalizedStatus === 'diff_found' || normalizedStatus === 'reviewed' || normalizedStatus === 'no_diff');
  const canRun = Boolean(onRun) && (!status || normalizedStatus === 'not_started' || normalizedStatus === 'failed' || normalizedStatus === 'rejected');
  const canCancel = Boolean(onCancel) && (normalizedStatus === 'pending' || normalizedStatus === 'failed' || normalizedStatus === 'rejected');
  const cancelLabel = normalizedStatus === 'pending'
    ? labels?.cancel || 'Cancel review'
    : labels?.clear || 'Clear review status';

  return (
    <TooltipProvider delayDuration={150}>
      <div className={cn('flex min-w-[150px] items-center justify-start gap-1.5', className)}>
        <div className="min-w-0 space-y-1">
          <Badge
            variant="outline"
            className={cn('h-6 gap-1.5 whitespace-nowrap px-2 font-medium shadow-none', config.badgeClass)}
          >
            {normalizedStatus === 'pending' ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <StatusIcon className="h-3 w-3" />
            )}
            {config.label}
          </Badge>
          <div className="max-w-[150px] truncate text-[11px] leading-none text-muted-foreground">
            {reviewedAt ? formatDate(reviewedAt) : config.description}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-0.5">
          {canView && (
            <IconButton
              label={labels?.view || (normalizedStatus === 'diff_found' ? 'Review differences' : 'View review report')}
              className={normalizedStatus === 'diff_found' ? 'text-amber-700 hover:bg-amber-50 hover:text-amber-800' : undefined}
              onClick={onView}
            >
              <Eye className="h-3.5 w-3.5" />
            </IconButton>
          )}
          {canRun && (
            <IconButton
              label={labels?.run || 'Run review'}
              className="text-primary hover:bg-primary/5 hover:text-primary"
              onClick={onRun}
            >
              <RefreshCcw className="h-3.5 w-3.5" />
            </IconButton>
          )}
          {canCancel && (
            <IconButton
              label={cancelLabel}
              className="text-destructive hover:bg-destructive/5 hover:text-destructive"
              onClick={onCancel}
            >
              {normalizedStatus === 'pending' ? <X className="h-3.5 w-3.5" /> : <RotateCcw className="h-3.5 w-3.5" />}
            </IconButton>
          )}
        </div>
      </div>
    </TooltipProvider>
  );
}
