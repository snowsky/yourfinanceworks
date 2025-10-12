import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Loader2, FileText, ArrowRight, Clock } from "lucide-react";
import { invoiceApi, Invoice } from "@/lib/api";
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { formatDate } from "@/lib/utils";

export function RecentInvoices() {
  const { t } = useTranslation();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchInvoices = async () => {
      setLoading(true);
      try {
        const data = await invoiceApi.getInvoices();
        // Sort by date and take only the most recent 5
        const sortedInvoices = [...data]
          .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
          .slice(0, 5);
        setInvoices(sortedInvoices);
      } catch (error) {
        console.error("Failed to fetch recent invoices:", error);
        toast.error("Failed to load recent invoices");
      } finally {
        setLoading(false);
      }
    };
    
    fetchInvoices();
  }, []);

  return (
    <Card className="col-span-1 border-l-4 border-l-secondary bg-gradient-to-br from-secondary/5 to-transparent hover:shadow-lg transition-all duration-300 h-full">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xl font-semibold flex items-center gap-2">
            <div className="p-2 rounded-lg bg-secondary/10">
              <FileText className="h-5 w-5 text-secondary" />
            </div>
            Recent Invoices
          </CardTitle>
          <Button asChild variant="ghost" size="sm">
            <Link to="/invoices" className="flex items-center gap-1">
              View All
              <ArrowRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex justify-center items-center h-48">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : invoices.length > 0 ? (
          <div className="space-y-3">
            {invoices.map((invoice) => (
              <div key={invoice.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <div className="font-medium">{invoice.number}</div>
                    <div className="text-sm text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDate(invoice.created_at)}
                    </div>
                  </div>
                </div>
                <div className="text-right space-y-1">
                  <div className="font-semibold">
                    <CurrencyDisplay amount={invoice.amount} currency={invoice.currency} />
                  </div>
                  <Badge className={
                    invoice.status === 'paid' ? 'status-paid' :
                    invoice.status === 'pending' ? 'status-pending' :
                    invoice.status === 'overdue' ? 'status-overdue' :
                    invoice.status === 'partially_paid' ? 'status-partially-paid' :
                    'bg-muted/50 text-muted-foreground'
                  }>
                    {t(`invoices.status.${invoice.status}`)}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">{t('dashboard.startCreatingInvoices')}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}