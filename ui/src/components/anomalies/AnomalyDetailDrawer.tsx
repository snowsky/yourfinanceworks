import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ExternalLink, ShieldCheck, ShieldX } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { anomaliesApi, type Anomaly } from '@/lib/api';
import { RISK_BADGE, STATUS_BADGE, entityHref, entityLabel, renderDetailEntries } from '@/lib/anomaly-ui';

interface Props {
  anomaly: Anomaly | null;
  open: boolean;
  onClose: () => void;
}

export function AnomalyDetailDrawer({ anomaly, open, onClose }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [note, setNote] = useState('');

  const resolve = useMutation({
    mutationFn: ({ status }: { status: 'confirmed' | 'dismissed' }) =>
      anomaliesApi.resolve(anomaly!.id, status, note || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      toast.success(t('anomalies.resolved'));
      setNote('');
      onClose();
    },
    onError: () => toast.error(t('anomalies.resolve_failed')),
  });

  const href = anomaly ? entityHref(anomaly) : null;
  const entries = anomaly ? renderDetailEntries(anomaly.details) : [];

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        {anomaly && (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Badge variant="outline" className={RISK_BADGE[anomaly.risk_level] ?? ''}>
                  {t(`dashboard.anomalies.level.${anomaly.risk_level}`, anomaly.risk_level)}
                </Badge>
                <Badge variant="outline" className={STATUS_BADGE[anomaly.status] ?? ''}>
                  {t(`anomalies.status.${anomaly.status}`, anomaly.status)}
                </Badge>
              </SheetTitle>
            </SheetHeader>

            <div className="mt-4 space-y-4">
              <div>
                <p className="text-sm font-medium">{anomaly.reason}</p>
                {anomaly.rule_id && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{anomaly.rule_id}</p>
                )}
              </div>

              {href && (
                <button
                  type="button"
                  onClick={() => navigate(href)}
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  {entityLabel(anomaly)}
                  <ExternalLink className="h-3 w-3" />
                </button>
              )}

              {entries.length > 0 && (
                <div className="rounded-lg border p-3">
                  <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
                    {t('anomalies.evidence')}
                  </p>
                  <dl className="space-y-1.5">
                    {entries.map((e) => (
                      <div key={e.label} className="grid grid-cols-3 gap-2 text-sm">
                        <dt className="capitalize text-muted-foreground">{e.label}</dt>
                        <dd className="col-span-2 whitespace-pre-wrap break-words font-mono text-xs">
                          {e.value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

              {anomaly.status !== 'open' && anomaly.resolution_note && (
                <p className="text-sm text-muted-foreground">
                  {t('anomalies.prior_note')}: {anomaly.resolution_note}
                </p>
              )}

              <Textarea
                rows={2}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={t('anomalies.note_placeholder')}
              />

              <div className="flex gap-2">
                <ProfessionalButton
                  variant="destructive"
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate({ status: 'confirmed' })}
                >
                  <ShieldX className="h-4 w-4" />
                  {t('anomalies.confirm_real')}
                </ProfessionalButton>
                <ProfessionalButton
                  variant="outline"
                  disabled={resolve.isPending}
                  onClick={() => resolve.mutate({ status: 'dismissed' })}
                >
                  <ShieldCheck className="h-4 w-4" />
                  {t('anomalies.dismiss_false')}
                </ProfessionalButton>
              </div>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
