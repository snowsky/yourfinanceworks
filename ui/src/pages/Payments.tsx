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
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('payments.title')}
          description={t('payments.description')}
        />

        <ProfessionalCard className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>{t('payments.payment_list')}</CardTitle>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('payments.search_placeholder')}
                    className="pl-8 w-full sm:w-[200px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="flex gap-2 items-center">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <Select value={methodFilter} onValueChange={setMethodFilter}>
                    <SelectTrigger className="w-full sm:w-[150px]">
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
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('payments.table.invoice')}</TableHead>
                    <TableHead>{t('payments.table.client')}</TableHead>
                    <TableHead>{t('payments.table.date')}</TableHead>
                    <TableHead>{t('payments.table.amount')}</TableHead>
                    <TableHead>{t('payments.table.method')}</TableHead>
                    <TableHead>{t('payments.table.status')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('payments.loading')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (filteredPayments || []).length > 0 ? (
                    (filteredPayments || []).map((payment) => (
                      <TableRow key={payment.id}>
                        <TableCell>{payment.invoice_number || 'N/A'}</TableCell>
                        <TableCell>{payment.client_name || 'N/A'}</TableCell>
                        <TableCell>{payment.payment_date ? new Date(payment.payment_date).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'N/A'} UTC</TableCell>
                        <TableCell>
                          <CurrencyDisplay amount={payment.amount || 0} currency={payment.currency || 'USD'} />
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">
                            {payment.payment_method || 'N/A'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize">
                            {payment.status || 'N/A'}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="h-auto p-0 border-none">
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
          </CardContent>
        </ProfessionalCard>
      </div>
    </AppLayout>
  );
};

export default Payments;
