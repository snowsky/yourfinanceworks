import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Search, Filter, Loader2, CreditCard } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { paymentApi, Payment } from "@/lib/api";
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { useTranslation } from 'react-i18next';
import { PageHeader } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";

const Payments = () => {
  const { t } = useTranslation();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [methodFilter, setMethodFilter] = useState("all");
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

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
        const data = await paymentApi.getPayments();
        setPayments(data);
      } catch (error) {
        console.error("Failed to fetch payments:", error);
        toast.error(t('payments.errors.load_failed'));
      } finally {
        setLoading(false);
      }
    };

    fetchPayments();
  }, [currentTenantId]); // Use state variable as dependency

  const filteredPayments = (payments || []).filter(payment => {
    const matchesSearch =
      (payment.invoice_number || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (payment.client_name || '').toLowerCase().includes(searchQuery.toLowerCase());

    const matchesMethod = methodFilter === "all" || payment.payment_method === methodFilter;

    return matchesSearch && matchesMethod;
  });

  return (
    <AppLayout>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="space-y-2">
            <h1 className="text-4xl font-bold tracking-tight text-foreground">{t('payments.title')}</h1>
            <p className="text-lg text-muted-foreground">{t('payments.description')}</p>
          </div>
        </div>

        <ProfessionalCard className="slide-in" variant="elevated">
          <div className="space-y-6">
            {/* Header with filters */}
            <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
              <div>
                <h2 className="text-2xl font-bold text-foreground">{t('payments.payment_list')}</h2>
                <p className="text-muted-foreground mt-1">Track and manage all your payments in one place</p>
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
                      <SelectItem value="system">{t('payments.payment_methods.system')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
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
            ) : (filteredPayments || []).length > 0 ? (
              <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                      <TableHead className="font-bold text-foreground">{t('payments.table.invoice')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.client')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.date')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.amount')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.method')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('payments.table.status')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(filteredPayments || []).map((payment) => (
                      <TableRow key={payment.id} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
                        <TableCell className="font-semibold text-foreground">{payment.invoice_number || 'N/A'}</TableCell>
                        <TableCell className="text-foreground">{payment.client_name || 'N/A'}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">{payment.payment_date ? new Date(payment.payment_date).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'N/A'} UTC</TableCell>
                        <TableCell className="font-semibold text-foreground">
                          <CurrencyDisplay amount={payment.amount || 0} currency={payment.currency || 'USD'} />
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize font-medium">
                            {payment.payment_method || 'N/A'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize font-medium">
                            {payment.status || 'N/A'}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 gap-4">
                <div className="p-4 rounded-full bg-muted/50">
                  <CreditCard className="h-10 w-10 text-muted-foreground/50" />
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-bold text-foreground mb-2">{t('payments.no_payments', 'No payments yet')}</h3>
                  <p className="text-muted-foreground max-w-sm mx-auto">
                    {t('payments.no_payments_description', 'No payments have been recorded yet. Payments will appear here once invoices are paid or manually marked as paid.')}
                  </p>
                </div>
              </div>
            )}
          </div>
        </ProfessionalCard>
      </div>
    </AppLayout>
  );
};

export default Payments;
