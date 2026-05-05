import { CalendarClock, UserCircle } from 'lucide-react';

interface CreatedAtByCellProps {
  createdAt?: string | null;
  createdByUsername?: string | null;
  createdByEmail?: string | null;
  locale: string;
  timezone: string;
  unknownLabel: string;
}

export function CreatedAtByCell({
  createdAt,
  createdByUsername,
  createdByEmail,
  locale,
  timezone,
  unknownLabel,
}: CreatedAtByCellProps) {
  const createdDate = createdAt ? new Date(createdAt) : null;
  const hasValidDate = Boolean(createdDate && !Number.isNaN(createdDate.getTime()));
  const creator = createdByUsername || createdByEmail || unknownLabel;

  const dateLabel = hasValidDate
    ? createdDate!.toLocaleDateString(locale, {
      timeZone: timezone,
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
    : 'N/A';
  const timeLabel = hasValidDate
    ? createdDate!.toLocaleTimeString(locale, {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
    })
    : '';
  const fullDateLabel = hasValidDate
    ? createdDate!.toLocaleString(locale, {
      timeZone: timezone,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
    : 'N/A';

  return (
    <div className="min-w-[150px] space-y-1.5" title={`${fullDateLabel} · ${creator}`}>
      <div className="flex min-w-0 items-center gap-1.5">
        <CalendarClock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <div className="truncate text-sm font-medium leading-none text-foreground">{dateLabel}</div>
          {timeLabel && (
            <div className="mt-1 text-[11px] leading-none text-muted-foreground">{timeLabel}</div>
          )}
        </div>
      </div>
      <div className="flex min-w-0 items-center gap-1.5 text-[11px] leading-none text-muted-foreground">
        <UserCircle className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{creator}</span>
      </div>
    </div>
  );
}
