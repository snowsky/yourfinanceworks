import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldAlert, ShieldCheck, ChevronLeft, ChevronRight, ExternalLink, Settings as SettingsIcon, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/hooks/useAuth';
import type { AnomalyRuleConfig, AnomalyRuleSettings } from '@/lib/api/anomalies';
import {
  ProfessionalCard,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardContent,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { FeatureGate } from '@/components/FeatureGate';
import { anomaliesApi } from '@/lib/api';
import { RISK_BADGE, STATUS_BADGE, entityHref, entityLabel } from '@/lib/anomaly-ui';
import { AnomalyDetailDrawer } from '@/components/anomalies/AnomalyDetailDrawer';

const PAGE_SIZE = 20;
const STATUSES = ['open', 'confirmed', 'dismissed'] as const;

const RULE_LABELS: Record<string, string> = {
  duplicate_billing: 'Duplicate Billing',
  rounding_anomaly: 'Rounding Anomaly',
  phantom_vendor: 'Phantom Vendor',
  threshold_splitting: 'Threshold Splitting',
  temporal_anomaly: 'Temporal Anomaly',
  description_mismatch: 'Description Mismatch',
  attachment_audit: 'Attachment Audit',
};

function DetectionSettingsPanel() {
  const { isAdmin, user } = useAuth();
  const canEdit = isAdmin || user?.is_superuser === true;
  const queryClient = useQueryClient();
  const [panelOpen, setPanelOpen] = useState(false);
  const [edited, setEdited] = useState<AnomalyRuleConfig | null>(null);

  const { data } = useQuery({
    queryKey: ['anomalies', 'config'],
    queryFn: () => anomaliesApi.getConfig(),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (data) setEdited(data);
  }, [data]);

  const { mutate: save, isPending } = useMutation({
    mutationFn: () => anomaliesApi.updateConfig(edited!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies', 'config'] });
      toast.success('Detection settings saved');
    },
    onError: () => toast.error('Failed to save settings'),
  });

  const updateRule = (ruleId: string, patch: Partial<AnomalyRuleSettings>) => {
    setEdited((prev) =>
      prev
        ? {
            ...prev,
            rules: {
              ...prev.rules,
              [ruleId]: { ...prev.rules[ruleId], ...patch },
            },
          }
        : prev,
    );
  };

  return (
    <ProfessionalCard variant="elevated" className="mb-4">
      <ProfessionalCardHeader
        className="cursor-pointer select-none"
        onClick={() => setPanelOpen((o) => !o)}
      >
        <ProfessionalCardTitle className="flex items-center gap-2 text-base font-semibold">
          <SettingsIcon className="h-4 w-4 text-muted-foreground" />
          Detection settings
          <span className="ml-auto text-muted-foreground">
            {panelOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </span>
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      {panelOpen && (
        <ProfessionalCardContent>
          {!edited ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-6">
              {/* Global min risk score */}
              <div className="flex items-center justify-between gap-4">
                <label className="text-sm font-medium">Minimum risk score to record</label>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={edited.min_risk_score}
                  onChange={(e) =>
                    setEdited((prev) =>
                      prev ? { ...prev, min_risk_score: Number(e.target.value) } : prev,
                    )
                  }
                  disabled={!canEdit}
                  className="w-24"
                />
              </div>

              {/* Per-rule controls */}
              <div className="space-y-3">
                {Object.entries(RULE_LABELS).map(([ruleId, label]) => {
                  const rule: AnomalyRuleSettings = edited.rules[ruleId] ?? { enabled: true };
                  return (
                    <div key={ruleId} className="rounded-md border p-3 space-y-3">
                      {/* Enabled toggle */}
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{label}</span>
                        <Switch
                          checked={rule.enabled}
                          onCheckedChange={(v) => updateRule(ruleId, { enabled: v })}
                          disabled={!canEdit}
                        />
                      </div>

                      {/* rounding_anomaly: min_amount */}
                      {ruleId === 'rounding_anomaly' && (
                        <div className="flex items-center gap-3">
                          <label className="text-xs text-muted-foreground w-36">Min amount</label>
                          <Input
                            type="number"
                            min={0}
                            step={0.01}
                            value={rule.min_amount ?? 0}
                            onChange={(e) =>
                              updateRule(ruleId, { min_amount: Number(e.target.value) })
                            }
                            disabled={!canEdit}
                            className="w-28"
                          />
                        </div>
                      )}

                      {/* threshold_splitting: min_count + proximity_pct */}
                      {ruleId === 'threshold_splitting' && (
                        <div className="space-y-2">
                          <div className="flex items-center gap-3">
                            <label className="text-xs text-muted-foreground w-36">Min count</label>
                            <Input
                              type="number"
                              min={2}
                              step={1}
                              value={rule.min_count ?? 2}
                              onChange={(e) =>
                                updateRule(ruleId, { min_count: Number(e.target.value) })
                              }
                              disabled={!canEdit}
                              className="w-28"
                            />
                          </div>
                          <div className="flex items-center gap-3">
                            <label className="text-xs text-muted-foreground w-36">
                              Proximity (0.5–1.0)
                            </label>
                            <Input
                              type="number"
                              min={0.5}
                              max={1.0}
                              step={0.01}
                              value={rule.proximity_pct ?? 0.9}
                              onChange={(e) =>
                                updateRule(ruleId, { proximity_pct: Number(e.target.value) })
                              }
                              disabled={!canEdit}
                              className="w-28"
                            />
                          </div>
                        </div>
                      )}

                      {/* temporal_anomaly: start_hour + end_hour + flag_weekend */}
                      {ruleId === 'temporal_anomaly' && (
                        <div className="space-y-2">
                          <div className="flex items-center gap-3">
                            <label className="text-xs text-muted-foreground w-36">
                              Start hour (0–23)
                            </label>
                            <Input
                              type="number"
                              min={0}
                              max={23}
                              step={1}
                              value={rule.start_hour ?? 0}
                              onChange={(e) =>
                                updateRule(ruleId, { start_hour: Number(e.target.value) })
                              }
                              disabled={!canEdit}
                              className="w-28"
                            />
                          </div>
                          <div className="flex items-center gap-3">
                            <label className="text-xs text-muted-foreground w-36">
                              End hour (0–23)
                            </label>
                            <Input
                              type="number"
                              min={0}
                              max={23}
                              step={1}
                              value={rule.end_hour ?? 23}
                              onChange={(e) =>
                                updateRule(ruleId, { end_hour: Number(e.target.value) })
                              }
                              disabled={!canEdit}
                              className="w-28"
                            />
                          </div>
                          <div className="flex items-center justify-between">
                            <label className="text-xs text-muted-foreground">Flag weekends</label>
                            <Switch
                              checked={rule.flag_weekend ?? false}
                              onCheckedChange={(v) => updateRule(ruleId, { flag_weekend: v })}
                              disabled={!canEdit}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {canEdit && (
                <ProfessionalButton onClick={() => save()} disabled={isPending}>
                  {isPending ? 'Saving…' : 'Save'}
                </ProfessionalButton>
              )}
            </div>
          )}
        </ProfessionalCardContent>
      )}
    </ProfessionalCard>
  );
}

function AnomaliesList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusTab, setStatusTab] = useState<(typeof STATUSES)[number]>('open');
  const [page, setPage] = useState(0);

  const selectedId = searchParams.get('selected');

  const { data, isLoading } = useQuery({
    queryKey: ['anomalies', 'page', statusTab, page],
    queryFn: () => anomaliesApi.list({ skip: page * PAGE_SIZE, limit: PAGE_SIZE, status: statusTab }),
    staleTime: 30_000,
  });

  // The selected anomaly: prefer the row already in the list; else fetch by id.
  const listItem = data?.items.find((a) => String(a.id) === selectedId) ?? null;
  const { data: fetched } = useQuery({
    queryKey: ['anomalies', 'detail', selectedId],
    queryFn: () => anomaliesApi.get(Number(selectedId)),
    enabled: !!selectedId && !listItem,
  });
  const selected = listItem ?? fetched ?? null;

  const openDrawer = (id: number) => {
    searchParams.set('selected', String(id));
    setSearchParams(searchParams, { replace: false });
  };
  const closeDrawer = () => {
    searchParams.delete('selected');
    setSearchParams(searchParams, { replace: false });
  };

  const total = data?.total ?? 0;
  const items = data?.items ?? [];
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2 text-base font-semibold">
          <ShieldAlert className="h-4 w-4 text-warning" />
          {t('anomalies.title')}
          {total > 0 && <Badge variant="outline" className="ml-1">{total}</Badge>}
        </ProfessionalCardTitle>
        <p className="text-sm text-muted-foreground">
          {t('anomalies.description', 'Items flagged by automated fraud and anomaly detection on your invoices, expenses and bank transactions.')}
        </p>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <Tabs
          value={statusTab}
          onValueChange={(v) => { setStatusTab(v as (typeof STATUSES)[number]); setPage(0); }}
          className="mb-4"
        >
          <TabsList>
            {STATUSES.map((s) => (
              <TabsTrigger key={s} value={s}>{t(`anomalies.tab.${s}`, s)}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12 text-center">
            <ShieldCheck className="h-10 w-10 text-success" />
            <p className="font-medium">{t('anomalies.empty_title')}</p>
            <p className="text-sm text-muted-foreground">
              {t('anomalies.empty_description', 'Nothing needs review right now. New flags appear here automatically.')}
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
                      <TableRow
                        key={a.id}
                        className="cursor-pointer"
                        onClick={() => openDrawer(a.id)}
                      >
                        <TableCell>
                          <Badge variant="outline" className={RISK_BADGE[a.risk_level] ?? ''}>
                            {t(`dashboard.anomalies.level.${a.risk_level}`, a.risk_level)}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-md">
                          <p className="text-sm">{a.reason}</p>
                          {a.rule_id && <p className="mt-0.5 text-xs text-muted-foreground">{a.rule_id}</p>}
                        </TableCell>
                        <TableCell>
                          {href ? (
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); navigate(href); }}
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
                          <Badge variant="outline" className={STATUS_BADGE[a.status] ?? ''}>
                            {t(`anomalies.status.${a.status}`, a.status)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {t('anomalies.page_of', { page: page + 1, pages: pageCount })}
              </p>
              <div className="flex items-center gap-2">
                <ProfessionalButton variant="outline" size="sm" disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}>
                  <ChevronLeft className="h-4 w-4" />{t('common.previous')}
                </ProfessionalButton>
                <ProfessionalButton variant="outline" size="sm" disabled={page + 1 >= pageCount}
                  onClick={() => setPage((p) => p + 1)}>
                  {t('common.next')}<ChevronRight className="h-4 w-4" />
                </ProfessionalButton>
              </div>
            </div>
          </>
        )}
      </ProfessionalCardContent>
      <AnomalyDetailDrawer anomaly={selected} open={!!selectedId} onClose={closeDrawer} />
    </ProfessionalCard>
  );
}

export default function Anomalies() {
  return (
    <FeatureGate feature="anomaly_detection" showUpgradePrompt>
      <DetectionSettingsPanel />
      <AnomaliesList />
    </FeatureGate>
  );
}
