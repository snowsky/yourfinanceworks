import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useFeatures } from '@/contexts/FeatureContext';
import { FeatureGate } from '@/components/FeatureGate';
import { PageHeader } from '@/components/ui/professional-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CashFlowTabContent } from '@/pages/CashFlow';
import { NetWorthTabContent } from '@/components/networth/NetWorthTabContent';
import { FinancesTabIntro } from '@/components/finances/FinancesTabIntro';

type TabKey = 'cashflow' | 'networth';

const Finances: React.FC = () => {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const [searchParams, setSearchParams] = useSearchParams();

  const cashflowEnabled = isFeatureEnabled('cash_flow');
  const networthEnabled = isFeatureEnabled('net_worth');

  const available: TabKey[] = [
    ...(cashflowEnabled ? (['cashflow'] as TabKey[]) : []),
    ...(networthEnabled ? (['networth'] as TabKey[]) : []),
  ];

  // Neither feature licensed: show the upgrade prompt (gate on cash_flow).
  if (available.length === 0) {
    return (
      <FeatureGate feature="cash_flow" showUpgradePrompt>
        <div />
      </FeatureGate>
    );
  }

  const requested = searchParams.get('tab') as TabKey | null;
  const active: TabKey =
    requested && available.includes(requested) ? requested : available[0];

  const onTabChange = (value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', value);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title={t('navigation.finances', { defaultValue: 'Finances' })}
        description={t('finances.subtitle', {
          defaultValue: 'Cash flow forecasting and your net worth in one place',
        })}
      />
      <Tabs value={active} onValueChange={onTabChange}>
        <TabsList>
          {cashflowEnabled ? <TabsTrigger value="cashflow">Cash Flow</TabsTrigger> : null}
          {networthEnabled ? <TabsTrigger value="networth">Net Worth</TabsTrigger> : null}
        </TabsList>
        {cashflowEnabled ? (
          <TabsContent value="cashflow" className="mt-6">
            <FinancesTabIntro
              storageKey="finances_intro_cashflow_dismissed"
              title="What's in Cash Flow"
              description="Projects money in and out so you can see your runway and plan ahead."
              sources={[
                'Unpaid invoices (money in)',
                'Recorded & recurring expenses (money out)',
                'Recurring bank-statement patterns',
              ]}
              output="Forecast, runway & scenario planning"
            />
            <CashFlowTabContent />
          </TabsContent>
        ) : null}
        {networthEnabled ? (
          <TabsContent value="networth" className="mt-6">
            <FinancesTabIntro
              storageKey="finances_intro_networth_dismissed"
              title="What's in Net Worth"
              description="Combines everything you own and owe into one number, tracked over time."
              sources={[
                'Bank balances (from statements)',
                'Investment portfolios (current value)',
                'Liabilities you add (cards, loans, mortgages)',
              ]}
              output="Net worth, per-account breakdown & trend"
            />
            <NetWorthTabContent />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
};

export default Finances;
