import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Wallet, Info, CheckCircle2 } from 'lucide-react';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { investmentApi, InvestmentPortfolio } from '@/lib/api';
import { toast } from 'sonner';
import FileUploadDialog from '@/components/investments/FileUploadDialog';
import FileAttachmentsList from '@/components/investments/FileAttachmentsList';

const CreatePortfolio: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  const [formData, setFormData] = useState({
    name: '',
    portfolio_type: 'taxable' as 'taxable' | 'retirement' | 'business',
    currency: 'USD'
  });
  const [createdPortfolioId, setCreatedPortfolioId] = useState<number | null>(null);
  const [showFileUploadDialog, setShowFileUploadDialog] = useState(false);

  const createPortfolioMutation = useMutation<InvestmentPortfolio, unknown, typeof formData>({
    mutationFn: (data: typeof formData) => investmentApi.create(data),
    onSuccess: async (portfolio) => {
      toast.success(t('Portfolio created successfully'));
      setCreatedPortfolioId(portfolio.id);
      setShowFileUploadDialog(true);
      await queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || t('Failed to create portfolio');
      toast.error(errorMessage);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      toast.error(t('Portfolio name is required'));
      return;
    }
    createPortfolioMutation.mutate(formData);
  };

  const handleFileUploadComplete = () => {
    setShowFileUploadDialog(false);
    navigate('/investments');
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <div className="flex items-center gap-4 mb-2">
        <ProfessionalButton asChild variant="ghost" size="sm" className="rounded-full h-10 w-10 p-0">
          <Link to="/investments">
            <ArrowLeft className="w-5 h-5" />
          </Link>
        </ProfessionalButton>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground font-medium">{t('Investments')}</span>
          <span className="text-muted-foreground/30 px-1">/</span>
          <span className="text-foreground font-semibold">{t('New Portfolio')}</span>
        </div>
      </div>

      <PageHeader
        title={t('Create New Portfolio')}
        description={t('Create a new investment portfolio to track your assets, transactions, and performance.')}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <ContentSection>
            <ProfessionalCard variant="elevated" className="border-border/40 shadow-xl overflow-hidden">
              <div className="bg-primary/5 p-6 border-b border-primary/10">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-2xl bg-primary text-white shadow-lg">
                    <Wallet className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-bold text-lg">{t('Portfolio Details')}</h3>
                    <p className="text-sm text-muted-foreground">{t('Enter the basic information for your new investment account.')}</p>
                  </div>
                </div>
              </div>

              <div className="p-8">
                <form onSubmit={handleSubmit} className="space-y-8">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div className="space-y-3">
                      <Label htmlFor="name" className="text-sm font-bold uppercase tracking-wider text-muted-foreground/70">
                        {t('Portfolio Name')}
                      </Label>
                      <Input
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder={t('e.g., Vanguard Retirement Account')}
                        className="h-12 rounded-xl border-border/50 focus:ring-primary/20 text-lg font-medium"
                        required
                        disabled={createPortfolioMutation.isPending}
                      />
                      <p className="text-xs text-muted-foreground">{t('A descriptive name to identify this portfolio.')}</p>
                    </div>

                    <div className="space-y-3">
                      <Label htmlFor="portfolio_type" className="text-sm font-bold uppercase tracking-wider text-muted-foreground/70">
                        {t('Account Type')}
                      </Label>
                      <Select
                        value={formData.portfolio_type}
                        onValueChange={(value: 'taxable' | 'retirement' | 'business') =>
                          setFormData({ ...formData, portfolio_type: value })
                        }
                        disabled={createPortfolioMutation.isPending}
                      >
                        <SelectTrigger className="h-12 rounded-xl border-border/50 text-base">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="rounded-xl shadow-2xl border-border/50">
                          <SelectItem value="taxable" className="rounded-lg m-1">{t('Taxable Brokerage')}</SelectItem>
                          <SelectItem value="retirement" className="rounded-lg m-1">{t('Retirement (401k, IRA)')}</SelectItem>
                          <SelectItem value="business" className="rounded-lg m-1">{t('Business Investment')}</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">{t('Affects tax reporting and performance benchmarks.')}</p>
                    </div>

                    <div className="space-y-3">
                      <Label htmlFor="currency" className="text-sm font-bold uppercase tracking-wider text-muted-foreground/70">
                        {t('Base Currency')}
                      </Label>
                      <Select
                        value={formData.currency}
                        onValueChange={(value) => setFormData({ ...formData, currency: value })}
                        disabled={createPortfolioMutation.isPending}
                      >
                        <SelectTrigger className="h-12 rounded-xl border-border/50 text-base">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="rounded-xl">
                          <SelectItem value="USD">USD - US Dollar</SelectItem>
                          <SelectItem value="EUR">EUR - Euro</SelectItem>
                          <SelectItem value="GBP">GBP - British Pound</SelectItem>
                          <SelectItem value="CAD">CAD - Canadian Dollar</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="pt-6 border-t border-border/30 flex flex-col sm:flex-row gap-4">
                    <ProfessionalButton
                      type="button"
                      variant="outline"
                      className="rounded-xl px-8 h-12 flex-1"
                      onClick={() => navigate('/investments')}
                      disabled={createPortfolioMutation.isPending}
                    >
                      {t('Cancel')}
                    </ProfessionalButton>
                    <ProfessionalButton
                      type="submit"
                      variant="gradient"
                      className="rounded-xl px-8 h-12 flex-1 shadow-lg shadow-primary/20"
                      loading={createPortfolioMutation.isPending}
                    >
                      {t('Create Portfolio')}
                    </ProfessionalButton>
                  </div>
                </form>
              </div>
            </ProfessionalCard>
          </ContentSection>
        </div>

        <div className="space-y-6">
          <ProfessionalCard className="border-border/40 bg-muted/20">
            <h4 className="font-bold mb-4 flex items-center gap-2">
              <Info className="w-4 h-4 text-primary" />
              {t('Tips')}
            </h4>
            <div className="space-y-4">
              <div className="flex gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                <p className="text-sm text-muted-foreground">
                  {t('Use specific names like "Fidelity ROTH IRA" for better organization.')}
                </p>
              </div>
              <div className="flex gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                <p className="text-sm text-muted-foreground">
                  {t('Portfolios can be archived later if you close the account.')}
                </p>
              </div>
              <div className="flex gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-500 flex-shrink-0" />
                <p className="text-sm text-muted-foreground">
                  {t('Multi-currency support allows tracking international investments.')}
                </p>
              </div>
            </div>
          </ProfessionalCard>

          <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-xl relative overflow-hidden">
            <div className="relative z-10">
              <h4 className="font-bold mb-2">{t('Why separate portfolios?')}</h4>
              <p className="text-sm text-slate-300 leading-relaxed">
                {t('Separating your investments allows for more accurate tax reporting and helps you track specific financial goals independently.')}
              </p>
            </div>
            <div className="absolute top-0 right-0 -mr-4 -mt-4 w-24 h-24 bg-white/5 rounded-full blur-2xl"></div>
          </div>
        </div>
      </div>

      {/* File Upload Dialog */}
      {createdPortfolioId && (
        <>
          <FileUploadDialog
            portfolioId={createdPortfolioId}
            open={showFileUploadDialog}
            onOpenChange={setShowFileUploadDialog}
            onUploadSuccess={handleFileUploadComplete}
          />

          {/* Show file attachments list after portfolio creation */}
          {!showFileUploadDialog && (
            <ContentSection>
              <FileAttachmentsList portfolioId={createdPortfolioId} />
            </ContentSection>
          )}
        </>
      )}
    </div>
  );
};

export default CreatePortfolio;