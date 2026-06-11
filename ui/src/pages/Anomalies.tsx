import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  ShieldAlert,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Check,
} from 'lucide-react';
import {
  ProfessionalCard,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardContent,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { FeatureGate } from '@/components/FeatureGate';
import { anomaliesApi } from '@/lib/api';
import { RISK_BADGE, entityHref, entityLabel } from '@/lib/anomaly-ui';

const PAGE_SIZE = 20;

function AnomaliesList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ['anomalies', 'page', page],
    queryFn: () => anomaliesApi.list({ skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
    staleTime: 30_000,
  });

  const dismiss = useMutation({
    mutationFn: (id: number) => anomaliesApi.dismiss(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      toast.success(t('dashboard.anomalies.dismissed'));
    },
    onError: () => toast.error(t('dashboard.anomalies.dismiss_failed')),
  });

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2 text-base font-semibold">
          <ShieldAlert className="h-4 w-4 text-warning" />
          {t('anomalies.title')}
          {total > 0 && (
            <Badge variant="outline" className="ml-1">
              {total}
            </Badge>
          )}
        </ProfessionalCardTitle>
        <p className="text-sm text-muted-foreground">
          {t(
            'anomalies.description',
            'Items flagged by automated fraud and anomaly detection on your invoices, expenses and bank transactions.'
          )}
        </p>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12 text-center">
            <ShieldCheck className="h-10 w-10 text-success" />
            <p className="font-medium">{t('anomalies.empty_title')}</p>
            <p className="text-sm text-muted-foreground">
              {t(
                'anomalies.empty_description',
                'Nothing needs review right now. New flags appear here automatically.'
              )}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">{t('anomalies.col_risk')}</TableHead>
                    <TableHead>{t('anomalies.col_issue')}</TableHead>
                    <TableHead className="w-44">{t('anomalies.col_item')}</TableHead>
                    <TableHead className="w-40">{t('anomalies.col_detected')}</TableHead>
                    <TableHead className="w-28 text-right">{t('anomalies.col_action')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((a) => {
                    const href = entityHref(a);
                    return (
                      <TableRow key={a.id}>
                        <TableCell>
                          <Badge variant="outline" className={RISK_BADGE[a.risk_level] ?? ''}>
                            {t(`dashboard.anomalies.level.${a.risk_level}`, a.risk_level)}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-md">
                          <p className="text-sm">{a.reason}</p>
                          {a.rule_id && (
                            <p className="mt-0.5 text-xs text-muted-foreground">{a.rule_id}</p>
                          )}
                        </TableCell>
                        <TableCell>
                          {href ? (
                            <button
                              type="button"
                              onClick={() => navigate(href)}
                              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                            >
                              {entityLabel(a)}
                              <ExternalLink className="h-3 w-3" />
                            </button>
                          ) : (
                            <span className="text-sm text-muted-foreground">{entityLabel(a)}</span>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          <ProfessionalButton
                            variant="ghost"
                            size="sm"
                            disabled={dismiss.isPending}
                            onClick={() => dismiss.mutate(a.id)}
                          >
                            <Check className="h-3.5 w-3.5" />
                            {t('anomalies.dismiss')}
                          </ProfessionalButton>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {t('anomalies.page_of', {
                  page: page + 1,
                  pages: pageCount,
                })}
              </p>
              <div className="flex items-center gap-2">
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                  {t('common.previous')}
                </ProfessionalButton>
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  disabled={page + 1 >= pageCount}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t('common.next')}
                  <ChevronRight className="h-4 w-4" />
                </ProfessionalButton>
              </div>
            </div>
          </>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}

export default function Anomalies() {
  return (
    <FeatureGate feature="anomaly_detection" showUpgradePrompt>
      <AnomaliesList />
    </FeatureGate>
  );
}
