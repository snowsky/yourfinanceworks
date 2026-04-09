import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, Filter, Loader2, CreditCard, ChevronLeft, ChevronRight, MoreHorizontal, Share2, Settings, Sparkles, ExternalLink } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { paymentApi, Payment, settingsApi, type PaymentSettings } from "@/lib/api";
import { ShareButton } from "@/components/sharing/ShareButton";
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { useTranslation } from 'react-i18next';
import { ProfessionalCard, ProfessionalCardContent, ProfessionalCardDescription, ProfessionalCardHeader, ProfessionalCardTitle } from "@/components/ui/professional-card";
import { useColumnVisibility, type ColumnDef } from "@/hooks/useColumnVisibility";
import { ColumnPicker } from "@/components/ui/column-picker";
import { getCurrentUser } from "@/utils/auth";

const PAYMENT_COLUMNS: ColumnDef[] = [
  { key: 'id', label: 'ID' },
  { key: 'invoice', label: 'Invoice', essential: true },
  { key: 'client', label: 'Client', essential: true },
  { key: 'date', label: 'Date', essential: true },
  { key: 'amount', label: 'Amount', essential: true },
  { key: 'currency', label: 'Currency' },
  { key: 'method', label: 'Method' },
  { key: 'reference', label: 'Reference' },
  { key: 'notes', label: 'Notes' },
  { key: 'status', label: 'Status', essential: true },
  { key: 'actions', label: 'Actions', essential: true },
];

const PAYMENT_SETTINGS_KEY = "payment_settings";

const defaultPaymentSettings: PaymentSettings = {
  provider: "stripe",
  stripe: {
    enabled: false,
    accountLabel: "",
    publishableKey: "",
    secretKey: "",
    webhookSecret: "",
  },
};

const normalizePaymentSettings = (value: unknown): PaymentSettings => {
  if (!value || typeof value !== "object") {
    return defaultPaymentSettings;
  }

  const raw = value as Partial<PaymentSettings>;

  return {
    provider: "stripe",
    stripe: {
      ...defaultPaymentSettings.stripe,
      ...(raw.stripe ?? {}),
    },
  };
};

const Payments = () => {
  const { t } = useTranslation();
  const currentUser = getCurrentUser();
  const isAdmin = currentUser?.role === "admin";
  const { isVisible, toggle, reset, hiddenCount } = useColumnVisibility('payments', PAYMENT_COLUMNS);
  const [sharePaymentId, setSharePaymentId] = useState<number | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [stripeSettings, setStripeSettings] = useState<PaymentSettings>(defaultPaymentSettings);
  const [stripeConfigured, setStripeConfigured] = useState(false);
  const [stripeSettingsLoading, setStripeSettingsLoading] = useState(isAdmin);
  const [recentStripePayments, setRecentStripePayments] = useState<Payment[]>([]);
  const [recentStripePaymentLoading, setRecentStripePaymentLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [methodFilter, setMethodFilter] = useState("all");
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

  const [isStripeHistoryOpen, setIsStripeHistoryOpen] = useState(false);
  const [stripeHistory, setStripeHistory] = useState<any[]>([]);
  const [stripeHistoryLoading, setStripeHistoryLoading] = useState(false);

  const fetchStripeHistory = async () => {
    setStripeHistoryLoading(true);
    try {
      const res = await paymentApi.getStripeHistory(30);
      if (res.success && res.data) {
        setStripeHistory(res.data);
      } else {
        setStripeHistory([]);
      }
    } catch (e) {
      console.error(e);
      toast.error("Failed to fetch Stripe history");
    } finally {
      setStripeHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (isStripeHistoryOpen) {
      fetchStripeHistory();
    }
  }, [isStripeHistoryOpen]);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const pageSize = 10;

  // Get current tenant ID to trigger refetch when organization switches
  const getCurrentTenantId = () => {
    try {
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        return selectedTenantId;
      }
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user?.tenant_id?.toString();
      }
    } catch (e) {
      console.error('Error getting tenant ID:', e);
    }
    return null;
  };

  // Update tenant ID when it changes
  useEffect(() => {
    const updateTenantId = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Payments: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
        setCurrentTenantId(tenantId);
        setCurrentPage(1); // Reset to first page on tenant change
      }
    };

    updateTenantId();

    // Listen for storage changes
    const handleStorageChange = () => {
      updateTenantId();
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [currentTenantId]);

  useEffect(() => {
    const fetchPayments = async () => {
      setLoading(true);
      try {
        const response = await paymentApi.getPayments({
          limit: pageSize,
          offset: (currentPage - 1) * pageSize
        });
        setPayments(response.data || []);
        setTotalCount(response.count || 0);
      } catch (error) {
        console.error("Failed to fetch payments:", error);
        toast.error(t('payments.errors.load_failed'));
      } finally {
        setLoading(false);
      }
    };

    fetchPayments();
  }, [currentTenantId, currentPage]); // Re-fetch on tenant or page change

  useEffect(() => {
    const fetchStripeSidebarData = async () => {
      if (!currentTenantId) {
        return;
      }

      setRecentStripePaymentLoading(true);
      setStripeSettingsLoading(isAdmin);

      try {
        const [recentStripeResponse, stripeSettingResponse] = await Promise.all([
          paymentApi.getPayments({ limit: 10, paymentMethod: "stripe" }),
          isAdmin ? settingsApi.getSetting(PAYMENT_SETTINGS_KEY) : Promise.resolve(null),
        ]);

        setRecentStripePayments(recentStripeResponse.data || []);

        if (stripeSettingResponse) {
          const nextSettings = normalizePaymentSettings(stripeSettingResponse.value);
          const configured = Boolean(
            nextSettings.stripe.enabled &&
              nextSettings.stripe.publishableKey.trim() &&
              nextSettings.stripe.secretKey.trim()
          );
          setStripeSettings(nextSettings);
          setStripeConfigured(configured);
        } else {
          setStripeConfigured(false);
        }
      } catch (error) {
        console.error("Failed to fetch Stripe sidebar data:", error);
      } finally {
        setRecentStripePaymentLoading(false);
        setStripeSettingsLoading(false);
      }
    };

    fetchStripeSidebarData();
  }, [currentTenantId, isAdmin]);

  const filteredPayments = (payments || []).filter(payment => {
    const matchesSearch =
      (payment.invoice_number || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (payment.client_name || '').toLowerCase().includes(searchQuery.toLowerCase());

    const matchesMethod = methodFilter === "all" || payment.payment_method === methodFilter;

    return matchesSearch && matchesMethod;
  });

  const totalPages = Math.ceil(totalCount / pageSize);
  const canShowStripePaymentCard = isAdmin ? stripeConfigured && recentStripePayments.length > 0 : recentStripePayments.length > 0;

  return (
    <div className="h-full space-y-8 fade-in">
      {/* Hero Header */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight">{t('payments.title')}</h1>
          <p className="text-lg text-muted-foreground">{t('payments.description')}</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <ProfessionalCard className="slide-in" variant="elevated">
          <div className="space-y-6">
          {/* Header with filters */}
          <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
            <div>
              <h2 className="text-2xl font-bold text-foreground">{t('payments.payment_list')}</h2>
              <p className="text-muted-foreground mt-1">{t('payments.manage_payments_description')}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
              {/* Search */}
              <div className="relative w-full sm:w-auto">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('payments.search_placeholder')}
                  className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              {/* Method Filter */}
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Select value={methodFilter} onValueChange={setMethodFilter}>
                  <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
                    <SelectValue placeholder={t('payments.filter_by_method')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('payments.all_methods')}</SelectItem>
                    <SelectItem value="credit_card">{t('payments.payment_methods.credit_card')}</SelectItem>
                    <SelectItem value="bank_transfer">{t('payments.payment_methods.bank_transfer')}</SelectItem>
                    <SelectItem value="cash">{t('payments.payment_methods.cash')}</SelectItem>
                    <SelectItem value="stripe">{t('payments.payment_methods.stripe')}</SelectItem>
                    <SelectItem value="system">{t('payments.payment_methods.system')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <ColumnPicker
                columns={PAYMENT_COLUMNS}
                isVisible={isVisible}
                onToggle={toggle}
                onReset={reset}
                hiddenCount={hiddenCount}
              />
            </div>
          </div>

          {/* Content */}
          {loading ? (
            <div className="flex justify-center items-center h-40">
              <div className="flex flex-col items-center gap-4">
                <div className="relative w-12 h-12">
                  <Loader2 className="h-12 w-12 animate-spin text-primary/60" />
                </div>
                <p className="text-muted-foreground font-medium">{t('payments.loading')}</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                      {isVisible('id') && <TableHead className="font-bold text-foreground">{t('common.id', { defaultValue: 'ID' })}</TableHead>}
                      <TableHead className="font-bold text-foreground">{t('payments.table.invoice')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.client')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.date')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.amount')}</TableHead>
                      {isVisible('currency') && <TableHead className="font-bold text-foreground">{t('payments.table.currency', { defaultValue: 'Currency' })}</TableHead>}
                      {isVisible('method') && <TableHead className="font-bold text-foreground">{t('payments.table.method')}</TableHead>}
                      {isVisible('reference') && <TableHead className="font-bold text-foreground">{t('payments.table.reference', { defaultValue: 'Reference' })}</TableHead>}
                      {isVisible('notes') && <TableHead className="font-bold text-foreground">{t('payments.table.notes', { defaultValue: 'Notes' })}</TableHead>}
                      <TableHead className="font-bold text-foreground">{t('payments.table.status')}</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPayments.length > 0 ? (
                      filteredPayments.map((payment) => (
                        <TableRow key={payment.id} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
                          {isVisible('id') && <TableCell className="font-mono text-sm text-muted-foreground">#{payment.id}</TableCell>}
                          <TableCell className="font-semibold text-foreground">
                            <Link
                              to={`/invoices/view/${payment.invoice_id}`}
                              className="text-primary hover:underline transition-all"
                            >
                              {payment.invoice_number || 'N/A'}
                            </Link>
                          </TableCell>
                          <TableCell className="text-foreground">{payment.client_name || 'N/A'}</TableCell>
                          <TableCell className="text-muted-foreground text-sm">{payment.payment_date ? new Date(payment.payment_date).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'N/A'} UTC</TableCell>
                          <TableCell className="font-semibold text-foreground">
                            <CurrencyDisplay amount={payment.amount || 0} currency={payment.currency || 'USD'} />
                          </TableCell>
                          {isVisible('currency') && <TableCell className="text-muted-foreground text-sm">{payment.currency || 'N/A'}</TableCell>}
                          {isVisible('method') && (
                            <TableCell>
                              <Badge variant="outline" className="capitalize font-medium">
                                {payment.payment_method || 'N/A'}
                              </Badge>
                            </TableCell>
                          )}
                          {isVisible('reference') && <TableCell className="text-muted-foreground text-sm font-mono">{payment.reference_number || '—'}</TableCell>}
                          {isVisible('notes') && <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">{payment.notes || '—'}</TableCell>}
                          <TableCell>
                            <Badge variant="outline" className="capitalize font-medium">
                              {payment.status || 'N/A'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => setSharePaymentId(payment.id)}>
                                  <Share2 className="mr-2 h-4 w-4" /> Share
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                            <ShareButton
                              recordType="payment"
                              recordId={payment.id}
                              open={sharePaymentId === payment.id}
                              onOpenChange={(isOpen: boolean) => { if (!isOpen) setSharePaymentId(null); }}
                            />
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={6 + (isVisible('id') ? 1 : 0) + (isVisible('currency') ? 1 : 0) + (isVisible('method') ? 1 : 0) + (isVisible('reference') ? 1 : 0) + (isVisible('notes') ? 1 : 0)} className="h-auto p-0 border-none">
                          <div className="text-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                            <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                              <CreditCard className="h-8 w-8 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold mb-2">{t('payments.no_payments', 'No payments yet')}</h3>
                            <p className="text-muted-foreground max-w-sm mx-auto">
                              {t('payments.no_payments_description', 'No payments have been recorded yet. Payments will appear here once invoices are paid or manually marked as paid.')}
                            </p>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination Controls */}
              {totalCount > pageSize && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-2 py-2">
                  <div className="text-sm text-muted-foreground order-2 sm:order-1">
                    {t('common.showing_of', {
                      count: filteredPayments.length,
                      total: totalCount,
                      defaultValue: `Showing ${filteredPayments.length} of ${totalCount} payments`
                    })}
                  </div>
                  <div className="flex items-center gap-2 order-1 sm:order-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                      disabled={currentPage === 1 || loading}
                      className="h-9 w-9 p-0"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <div className="flex items-center px-4 text-sm font-medium bg-muted/30 h-9 rounded-lg border border-border/50">
                      {t('common.page_of', {
                        current: currentPage,
                        total: totalPages,
                        defaultValue: `Page ${currentPage} of ${totalPages}`
                      })}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                      disabled={currentPage === totalPages || loading}
                      className="h-9 w-9 p-0"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
          </div>
        </ProfessionalCard>

        <div className="space-y-6 xl:sticky xl:top-6 self-start">
          <ProfessionalCard variant="elevated">
            <ProfessionalCardHeader>
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <ProfessionalCardTitle className="flex items-center gap-2 text-xl">
                    <Sparkles className="h-5 w-5 text-primary" />
                    {t("payments.stripe_sidebar.title", "Stripe")}
                  </ProfessionalCardTitle>
                  <ProfessionalCardDescription>
                    {t(
                      "payments.stripe_sidebar.description",
                      "A quick view of your Stripe setup and latest Stripe payments."
                    )}
                  </ProfessionalCardDescription>
                </div>
              </div>
            </ProfessionalCardHeader>

            <ProfessionalCardContent className="space-y-4">
              {(stripeSettingsLoading || recentStripePaymentLoading) ? (
                <div className="flex items-center gap-3 rounded-xl border border-border/50 bg-muted/20 p-4 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>{t("payments.stripe_sidebar.loading", "Loading Stripe details...")}</span>
                </div>
              ) : (
                <>
                  {canShowStripePaymentCard && recentStripePayments.length > 0 ? (
                    <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
                       {recentStripePayments.map(payment => (
                       <div key={payment.id} className="space-y-4 rounded-xl border border-border/50 bg-muted/20 p-4">
                         <div className="flex items-center justify-between gap-2">
                           <p className="font-medium text-foreground">
                             {stripeSettings.stripe.accountLabel || t("payments.payment_methods.stripe")}
                           </p>
                           <Badge>
                             {stripeConfigured
                               ? t("settings.payment_settings.configured", "Configured")
                               : t("payments.payment_methods.stripe")}
                           </Badge>
                         </div>
     
                         <div className="space-y-2 text-sm">
                           <div className="flex items-center justify-between gap-3">
                             <span className="text-muted-foreground">{t("payments.table.amount")}</span>
                             <span className="font-semibold text-foreground">
                               <CurrencyDisplay
                                 amount={payment.amount || 0}
                                 currency={payment.currency || "USD"}
                               />
                             </span>
                           </div>
                           <div className="flex items-center justify-between gap-3">
                             <span className="text-muted-foreground">{t("payments.table.client")}</span>
                             <span className="font-medium text-foreground">{payment.client_name || "N/A"}</span>
                           </div>
                           <div className="flex items-center justify-between gap-3">
                             <span className="text-muted-foreground">{t("payments.table.invoice")}</span>
                             <span className="font-medium text-foreground">{payment.invoice_number || "N/A"}</span>
                           </div>
                           <div className="flex items-center justify-between gap-3">
                             <span className="text-muted-foreground">{t("payments.table.date")}</span>
                             <span className="font-medium text-foreground">
                               {payment.payment_date
                                 ? new Date(payment.payment_date).toLocaleDateString()
                                 : "N/A"}
                             </span>
                           </div>
                         </div>
     
                         <Button asChild variant="outline" className="w-full">
                           <Link to={`/invoices/view/${payment.invoice_id}`}>
                             <ExternalLink className="mr-2 h-4 w-4" />
                             {t("payments.stripe_sidebar.open_invoice", "Open invoice")}
                           </Link>
                         </Button>
                       </div>
                       ))}
                    </div>
                  ) : stripeConfigured ? (
                    <div className="space-y-3 rounded-xl border border-dashed border-border/60 bg-muted/10 p-4">
                      <Badge>{t("settings.payment_settings.configured", "Configured")}</Badge>
                      <p className="text-sm text-muted-foreground">
                        {t(
                          "payments.stripe_sidebar.no_recent_payment",
                          "Stripe is configured. Your latest Stripe payments will appear here once recorded."
                        )}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4 rounded-xl border border-dashed border-primary/30 bg-primary/5 p-4">
                      <div className="space-y-2">
                        <p className="font-medium text-foreground">
                          {t("payments.stripe_sidebar.not_configured_title", "Stripe is not configured")}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {t(
                            "payments.stripe_sidebar.not_configured_description",
                            "Configure Stripe in Payment Settings to surface your latest Stripe activity here."
                          )}
                        </p>
                      </div>
                      {isAdmin ? (
                        <Button asChild className="w-full">
                          <Link to="/settings?tab=payments">
                            <Settings className="mr-2 h-4 w-4" />
                            {t("payments.stripe_sidebar.configure", "Configure Stripe")}
                          </Link>
                        </Button>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          {t(
                            "payments.stripe_sidebar.ask_admin",
                            "Ask an administrator to configure Stripe in Settings."
                          )}
                        </p>
                      )}
                    </div>
                  )}

                  {stripeConfigured && (
                    <Dialog open={isStripeHistoryOpen} onOpenChange={setIsStripeHistoryOpen}>
                      <DialogTrigger asChild>
                        <Button variant="outline" className="w-full">
                          View Stripe Account History
                        </Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
                        <DialogHeader>
                          <DialogTitle>Stripe Account History</DialogTitle>
                          <DialogDescription>Your latest 30 charges synced directly from Stripe.</DialogDescription>
                        </DialogHeader>
                        <div className="flex-1 overflow-auto mt-4 px-1">
                          {stripeHistoryLoading ? (
                            <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
                          ) : stripeHistory.length === 0 ? (
                            <div className="text-center p-8 text-muted-foreground">No recent charges found on Stripe.</div>
                          ) : (
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead>Date</TableHead>
                                  <TableHead>Description</TableHead>
                                  <TableHead>Customer</TableHead>
                                  <TableHead>Amount</TableHead>
                                  <TableHead>Status</TableHead>
                                  <TableHead></TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {stripeHistory.map(charge => (
                                  <TableRow key={charge.id}>
                                    <TableCell>{new Date(charge.payment_date).toLocaleDateString()}</TableCell>
                                    <TableCell>{charge.description || "—"}</TableCell>
                                    <TableCell>{charge.client_name || "—"}</TableCell>
                                    <TableCell>
                                      <CurrencyDisplay amount={charge.amount} currency={charge.currency} />
                                    </TableCell>
                                    <TableCell>
                                      <Badge variant="outline">{charge.status}</Badge>
                                    </TableCell>
                                    <TableCell className="text-right">
                                      {charge.receipt_url && (
                                        <a href={charge.receipt_url} target="_blank" rel="noopener noreferrer">
                                          <Button variant="ghost" size="sm">Receipt <ExternalLink className="ml-2 h-4 w-4" /></Button>
                                        </a>
                                      )}
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          )}
                        </div>
                      </DialogContent>
                    </Dialog>
                  )}
                </>
              )}
            </ProfessionalCardContent>
          </ProfessionalCard>
        </div>
      </div>
    </div>
  );
};

export default Payments;
