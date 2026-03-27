import React, { useState, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { AlertTriangle, Database, Eye, RotateCcw, Shield, ShieldCheck } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useTranslation } from 'react-i18next';
import { useFeatures } from '@/contexts/FeatureContext';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { FeatureGate } from '@/components/FeatureGate';
import { apiRequest } from '../../lib/api';
import { toast } from 'sonner';
import type { Anomaly } from './types';

interface AnomaliesTabProps {
  onTotalChange: (total: number) => void;
}

export const AnomaliesTab: React.FC<AnomaliesTabProps> = ({ onTotalChange }) => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { isFeatureEnabled } = useFeatures();
  const isAnomaliesEnabled = isFeatureEnabled('anomaly_detection');

  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null);
  const [anomaliesPage, setAnomaliesPage] = useState(1);
  const [anomaliesPageSize, setAnomaliesPageSize] = useState(20);
  const [totalAnomalies, setTotalAnomalies] = useState(0);

  const fetchAnomalies = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      const skip = (anomaliesPage - 1) * anomaliesPageSize;
      params.set('skip', skip.toString());
      params.set('limit', anomaliesPageSize.toString());

      const data = await apiRequest<{
        items: Anomaly[];
        total: number;
        skip: number;
        limit: number;
      }>(`/super-admin/anomalies?${params.toString()}`, {}, { skipTenant: true });

      setAnomalies(data.items || []);
      const total = data.total || 0;
      setTotalAnomalies(total);
      onTotalChange(total);
    } catch (err) {
      console.error('Failed to fetch anomalies:', err);
      setAnomalies([]);
      setTotalAnomalies(0);
      onTotalChange(0);
    }
  }, [anomaliesPage, anomaliesPageSize, onTotalChange]);

  useEffect(() => {
    if (isAnomaliesEnabled) {
      fetchAnomalies();
    }
  }, [anomaliesPage, anomaliesPageSize, isAnomaliesEnabled]);

  const handleRunAudit = async () => {
    try {
      const result = await apiRequest<{ message: string }>(
        '/super-admin/anomalies/audit',
        { method: 'POST' },
        { skipTenant: true },
      );
      toast.success(result.message);
      fetchAnomalies();
    } catch (err) {
      toast.error('Failed to trigger platform audit scan');
    }
  };

  const handleReprocessAll = async () => {
    try {
      const result = await apiRequest<{ message: string }>(
        '/super-admin/anomalies/reprocess',
        { method: 'POST' },
        { skipTenant: true },
      );
      toast.success(result.message);
      fetchAnomalies();
    } catch (err) {
      toast.error('Failed to trigger reprocess scan');
    }
  };

  return (
    <>
      <FeatureGate
        feature="anomaly_detection"
        fallback={
          <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
            <div className="p-12 text-center">
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                <AlertTriangle className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-2xl font-bold text-foreground mb-3">{t('superAdmin.business_license_required')}</h3>
              <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
                {t('superAdmin.business_license_description')}
              </p>
              <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
                <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  {t('superAdmin.with_business_license_get')}
                </h4>
                <ul className="text-left space-y-3 text-sm text-foreground/80">
                  <li className="flex items-start">
                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                    <span>{t('superAdmin.ai_powered_anomaly_detection')}</span>
                  </li>
                  <li className="flex items-start">
                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                    <span>{t('superAdmin.senior_forensic_auditor_ai')}</span>
                  </li>
                  <li className="flex items-start">
                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                    <span>{t('superAdmin.risk_scoring_intelligent_fraud_detection')}</span>
                  </li>
                  <li className="flex items-start">
                    <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                    <span>{t('superAdmin.cross_tenant_anomaly_monitoring')}</span>
                  </li>
                </ul>
              </div>
              <div className="flex justify-center gap-4">
                <Button
                  className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white"
                  onClick={() => window.location.href = '/settings?tab=license'}
                  size="lg"
                >
                  {t('superAdmin.upgrade_to_business_license')}
                </Button>
              </div>
            </div>
          </ProfessionalCard>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="lg:col-span-3">
            <ProfessionalCard className="slide-in">
              <div className="p-6">
                <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    <h2 className="text-xl font-semibold">{t('superAdmin.flagged_high_risk_items')}</h2>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={fetchAnomalies}>
                      <Database className="h-4 w-4 mr-2" />
                      {t('superAdmin.refresh_list')}
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleReprocessAll} className="bg-orange-600 hover:bg-orange-700 text-white">
                      <RotateCcw className="h-4 w-4 mr-2" />
                      {t('superAdmin.reprocess_all')}
                    </Button>
                    <Button variant="default" size="sm" onClick={handleRunAudit} className="bg-red-600 hover:bg-red-700 text-white">
                      <ShieldCheck className="h-4 w-4 mr-2" />
                      {t('superAdmin.run_audit_scan')}
                    </Button>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead>Organization</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Risk Level</TableHead>
                        <TableHead>Audit Reason</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {anomalies.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                            {t('superAdmin.no_high_risk_items')}
                          </TableCell>
                        </TableRow>
                      ) : (
                        anomalies.map((anomaly) => (
                          <TableRow key={`${anomaly.tenant_id}-${anomaly.id}`}>
                            <TableCell className="whitespace-nowrap">
                              {new Date(anomaly.created_at).toLocaleDateString()}
                            </TableCell>
                            <TableCell className="font-medium">{anomaly.tenant_name}</TableCell>
                            <TableCell className="capitalize">{anomaly.entity_type.replace('_', ' ')}</TableCell>
                            <TableCell>
                              <Badge variant={
                                anomaly.risk_level === 'critical' || anomaly.risk_level === 'high'
                                  ? 'destructive'
                                  : anomaly.risk_level === 'medium'
                                    ? 'default'
                                    : 'secondary'
                              }>
                                {anomaly.risk_level}
                              </Badge>
                            </TableCell>
                            <TableCell className="max-w-md truncate" title={anomaly.reason}>
                              {anomaly.reason}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button variant="ghost" size="sm" onClick={() => setSelectedAnomaly(anomaly)}>
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>

                  {/* Pagination */}
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-border/50">
                    <div className="text-sm text-muted-foreground">
                      Showing <span className="font-medium text-foreground">{anomalies.length}</span> of <span className="font-medium text-foreground">{totalAnomalies}</span> results
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setAnomaliesPage(prev => Math.max(1, prev - 1))}
                        disabled={anomaliesPage <= 1}
                        className="h-9 px-4"
                      >
                        {t('common.previous')}
                      </Button>
                      <div className="flex items-center gap-1">
                        {Array.from({ length: Math.ceil(totalAnomalies / anomaliesPageSize) }, (_, i) => i + 1)
                          .filter(p => p === 1 || p === Math.ceil(totalAnomalies / anomaliesPageSize) || Math.abs(p - anomaliesPage) <= 1)
                          .map((p, i, arr) => (
                            <div key={p} className="flex items-center">
                              {i > 0 && arr[i - 1] !== p - 1 && <span className="text-muted-foreground px-1">...</span>}
                              <Button
                                variant={anomaliesPage === p ? 'default' : 'outline'}
                                size="sm"
                                onClick={() => setAnomaliesPage(p)}
                                className="h-9 w-9 p-0"
                              >
                                {p}
                              </Button>
                            </div>
                          ))}
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setAnomaliesPage(prev => Math.min(Math.ceil(totalAnomalies / anomaliesPageSize), prev + 1))}
                        disabled={anomaliesPage >= Math.ceil(totalAnomalies / anomaliesPageSize)}
                        className="h-9 px-4"
                      >
                        {t('common.next')}
                      </Button>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
                      <Select value={String(anomaliesPageSize)} onValueChange={(v) => { setAnomaliesPageSize(Number(v)); setAnomaliesPage(1); }}>
                        <SelectTrigger className="w-[100px] h-10 rounded-lg border-border/50 bg-muted/30">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="10">10</SelectItem>
                          <SelectItem value="20">20</SelectItem>
                          <SelectItem value="50">50</SelectItem>
                          <SelectItem value="100">100</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            </ProfessionalCard>
          </div>

          <div className="lg:col-span-1">
            <ProfessionalCard className="bg-primary/5 border-primary/20 sticky top-6 slide-in">
              <div className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold text-primary">{t('superAdmin.auditor_recommendations')}</h3>
                </div>
                <div className="space-y-4">
                  <div className="text-sm">
                    <p className="font-medium text-primary/80 mb-1">{t('superAdmin.recommended_next_steps')}</p>
                    <ul className="list-disc pl-4 space-y-2 text-muted-foreground">
                      <li>{t('superAdmin.review_digital_audit_trail')}</li>
                      <li>{t('superAdmin.correlate_round_number_trends')}</li>
                      <li>{t('superAdmin.verify_physical_receipts')}</li>
                      <li>{t('superAdmin.cross_reference_split_transactions')}</li>
                    </ul>
                  </div>
                  <div className="pt-4 border-t border-primary/10">
                    <div className="p-3 bg-white/50 dark:bg-black/20 rounded-lg border border-primary/10">
                      <p className="text-[10px] uppercase tracking-wider font-bold text-primary/60 mb-1">{t('superAdmin.ai_insights_status')}</p>
                      <div className="flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                        <span className="text-xs font-medium">{t('superAdmin.senior_forensic_auditor_active')}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </ProfessionalCard>
          </div>
        </div>
      </FeatureGate>

      {/* Anomaly Details Dialog */}
      <Dialog open={!!selectedAnomaly} onOpenChange={open => { if (!open) setSelectedAnomaly(null); }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              Anomaly Details
            </DialogTitle>
          </DialogHeader>
          {selectedAnomaly && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Organization</Label>
                  <p className="font-semibold">{selectedAnomaly.tenant_name}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Entity Type</Label>
                  <p className="font-semibold capitalize">{selectedAnomaly.entity_type.replace('_', ' ')}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Entity ID</Label>
                  <p className="font-semibold">{selectedAnomaly.entity_id}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium text-muted-foreground">Detected On</Label>
                  <p className="font-semibold">{new Date(selectedAnomaly.created_at).toLocaleDateString()}</p>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Risk Assessment</Label>
                <div className="flex items-center gap-4">
                  <Badge variant={
                    selectedAnomaly.risk_level === 'critical' || selectedAnomaly.risk_level === 'high'
                      ? 'destructive'
                      : selectedAnomaly.risk_level === 'medium'
                        ? 'default'
                        : 'secondary'
                  }>
                    {selectedAnomaly.risk_level.toUpperCase()}
                  </Badge>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Risk Score:</span>
                    <span className="font-semibold">{selectedAnomaly.risk_score}/100</span>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Detection Rule</Label>
                <p className="font-mono text-sm bg-muted/50 p-2 rounded">{selectedAnomaly.rule_id}</p>
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Anomaly Reason</Label>
                <p className="text-sm leading-relaxed">{selectedAnomaly.reason}</p>
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium text-muted-foreground">Search Information</Label>
                <div className="bg-muted/30 p-3 rounded-lg">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="font-medium">Record Type:</span>
                      <span className="ml-2 capitalize">{selectedAnomaly.entity_type.replace('_', ' ')}</span>
                    </div>
                    <div>
                      <span className="font-medium">Record ID:</span>
                      <span className="ml-2">{selectedAnomaly.entity_id}</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Use this information to search for the record in the respective {selectedAnomaly.entity_type.replace('_', ' ')} section.
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="secondary" onClick={() => setSelectedAnomaly(null)}>
                  Close
                </Button>
                {(() => {
                  const currentTenantId = localStorage.getItem('selected_tenant_id') || user?.tenant_id?.toString();
                  const isFromCurrentTenant = selectedAnomaly.tenant_id.toString() === currentTenantId;
                  if (isFromCurrentTenant) {
                    return (
                      <Button
                        onClick={() => {
                          const path = `/${selectedAnomaly.entity_type}s/view/${selectedAnomaly.entity_id}`;
                          window.open(path, '_blank');
                        }}
                      >
                        Investigate Entity
                      </Button>
                    );
                  }
                  return (
                    <Button
                      variant="outline"
                      disabled
                      title={`This anomaly is from ${selectedAnomaly.tenant_name}. Switch to that organization to investigate.`}
                    >
                      Investigate Entity
                    </Button>
                  );
                })()}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};
