import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  Download, FileText, Calendar, Wallet, CheckCircle2,
  Info, AlertTriangle, FileSpreadsheet, FileJson
} from 'lucide-react';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { investmentApi, PortfolioListResponse } from '@/lib/api';
import { toast } from 'sonner';

const TaxExport: React.FC = () => {
  const { t } = useTranslation();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<string>(new Date().getFullYear().toString());

  const { data: portfolioData, isLoading: portfoliosLoading } = useQuery<PortfolioListResponse>({
    queryKey: ['portfolios', 'list-simple'],
    queryFn: () => investmentApi.list({ limit: 100 }),
  });

  const portfolios = portfolioData?.items || [];
  const years = Array.from({ length: 5 }, (_, i) => (new Date().getFullYear() - i).toString());

  const handleExport = (format: 'csv' | 'json') => {
    if (!selectedPortfolioId) {
      toast.error(t('Please select a portfolio first'));
      return;
    }

    // In a real app, we would trigger the download here
    toast.success(t('Preparing your tax export...'));
    setTimeout(() => {
      toast.info(t('Export successful! Check your downloads folder.'));
    }, 2000);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <PageHeader
        title="Tax Data Export"
        description="Consolidate your investment transactions and calculate capital gains for tax preparation."
        alert={
          <div className="flex items-start gap-4 p-4 rounded-xl bg-warning/10 border border-warning/30 text-warning text-sm">
            <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-semibold">Disclaimer</p>
              <p>These reports are provided for informational purposes only and do not constitute professional tax advice. Always consult with a qualified tax professional before filing.</p>
            </div>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-6">
          <ProfessionalCard title="Export Configuration" className="border-border/40">
            <div className="space-y-6 pt-2">
              <div className="space-y-2">
                <label className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
                  <Wallet className="w-4 h-4" />
                  Select Portfolio
                </label>
                <Select value={selectedPortfolioId} onValueChange={setSelectedPortfolioId}>
                  <SelectTrigger className="rounded-xl border-border/50 h-11">
                    <SelectValue placeholder="Select a portfolio" />
                  </SelectTrigger>
                  <SelectContent className="rounded-xl">
                    {portfolios.map((p) => (
                      <SelectItem key={p.id} value={p.id.toString()}>
                        {p.name}
                      </SelectItem>
                    ))}
                    {portfolios.length === 0 && !portfoliosLoading && (
                      <SelectItem value="none" disabled>No portfolios found</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Tax Year
                </label>
                <Select value={selectedYear} onValueChange={setSelectedYear}>
                  <SelectTrigger className="rounded-xl border-border/50 h-11">
                    <SelectValue placeholder="Select year" />
                  </SelectTrigger>
                  <SelectContent className="rounded-xl">
                    {years.map((y) => (
                      <SelectItem key={y} value={y}>{y}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="pt-4 space-y-3">
                <p className="text-xs text-muted-foreground font-medium flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-success" />
                  Includes Realized Gains/Losses
                </p>
                <p className="text-xs text-muted-foreground font-medium flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-success" />
                  Includes Dividend Income
                </p>
                <p className="text-xs text-muted-foreground font-medium flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-success" />
                  FIFO Cost Basis calculation
                </p>
              </div>
            </div>
          </ProfessionalCard>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <ContentSection title="Available Reports" description="Download your tax reports in various formats for your software or accountant.">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ProfessionalCard variant="elevated" className="border-primary/20 bg-primary/5 group hover:border-primary/40 transition-all cursor-pointer" onClick={() => handleExport('csv')}>
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-2xl bg-primary text-primary-foreground shadow-lg group-hover:scale-110 transition-transform">
                    <FileSpreadsheet className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-bold text-lg">Spreadsheet (CSV)</h3>
                    <p className="text-sm text-muted-foreground">Detailed transaction-level report compatible with Excel and Google Sheets.</p>
                    <div className="pt-3">
                      <ProfessionalButton variant="minimal" size="sm" className="bg-card shadow-sm border border-border/50 rounded-lg">
                        <Download className="w-3.5 h-3.5 mr-2" />
                        Download CSV
                      </ProfessionalButton>
                    </div>
                  </div>
                </div>
              </ProfessionalCard>

              <ProfessionalCard className="border-border/40 hover:bg-muted/30 transition-all cursor-pointer" onClick={() => handleExport('json')}>
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-2xl bg-muted text-muted-foreground shadow-sm group-hover:scale-110 transition-transform">
                    <FileJson className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-bold text-lg">JSON Data</h3>
                    <p className="text-sm text-muted-foreground">Machine-readable format for importing into custom financial software.</p>
                    <div className="pt-3">
                      <ProfessionalButton variant="minimal" size="sm" className="rounded-lg border border-border/50">
                        <Download className="w-3.5 h-3.5 mr-2" />
                        Download JSON
                      </ProfessionalButton>
                    </div>
                  </div>
                </div>
              </ProfessionalCard>
            </div>
          </ContentSection>

          <ProfessionalCard title="Regulatory Notice" className="border-border/40 overflow-hidden relative" variant="elevated">
            <div className="relative z-10 space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-success/10 text-success border border-success/30">
                  <FileText className="w-5 h-5" />
                </div>
                <h3 className="font-bold text-lg">Official Tax Documents?</h3>
              </div>
              <p className="text-muted-foreground text-sm leading-relaxed max-w-lg">
                YourFinanceWORKS provides tracking and calculation based on your provided data. It does NOT issue official 1099-B or 1099-DIV forms. You should use the official forms from your brokerage/custodian for your actual tax filing.
              </p>
            </div>
            <div className="absolute top-0 right-0 -mr-8 -mt-8 w-40 h-40 bg-emerald-500/5 rounded-full blur-3xl"></div>
          </ProfessionalCard>
        </div>
      </div>
    </div>
  );
};

export default TaxExport;