import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Loader2 } from "lucide-react";
import { invoiceApi, Invoice } from "@/lib/api";
import { toast } from "sonner";

export function InvoiceChart() {
  const [chartData, setChartData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchInvoices = async () => {
      setLoading(true);
      try {
        const data = await invoiceApi.getInvoices();
        console.log('Fetched invoices for chart:', data);
        prepareChartData(data);
      } catch (error) {
        console.error("Failed to fetch invoices for chart:", error);
        toast.error("Failed to load invoice data for chart");
      } finally {
        setLoading(false);
      }
    };
    
    fetchInvoices();
  }, []);

  const prepareChartData = (invoiceData: Invoice[]) => {
    console.log('Preparing chart data for invoices:', invoiceData);
    // Prepare data for chart
    const chartData = Array(6).fill(0).map((_, index) => {
      const month = new Date();
      month.setMonth(month.getMonth() - 5 + index);
      const monthName = month.toLocaleString('default', { month: 'short' });
      const year = month.getFullYear().toString().slice(2);
      const label = `${monthName} '${year}`;
      const startOfMonth = new Date(month.getFullYear(), month.getMonth(), 1);
      const endOfMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0);
      console.log('Bar:', label, 'Start:', startOfMonth, 'End:', endOfMonth);
      // Get invoices for this month
      const monthInvoices = invoiceData.filter(invoice => {
        const invoiceDate = new Date(invoice.date || invoice.created_at);
        console.log('Invoice:', invoice.number, 'Date:', invoice.date, 'Created:', invoice.created_at, 'Parsed:', invoiceDate);
        if (isNaN(invoiceDate.getTime())) return false;
        return invoiceDate >= startOfMonth && invoiceDate <= endOfMonth;
      });
      console.log('Invoices for', label, ':', monthInvoices);
      // Calculate totals
      const paid = monthInvoices
        .filter(inv => inv.status === 'paid')
        .reduce((sum, inv) => sum + inv.amount, 0);
      const pending = monthInvoices
        .filter(inv => inv.status === 'pending')
        .reduce((sum, inv) => sum + inv.amount, 0);
      return {
        name: label,
        paid: parseFloat(paid.toFixed(2)),
        pending: parseFloat(pending.toFixed(2))
      };
    });
    console.log('Final chart data:', chartData);
    setChartData(chartData);
  };

  return (
    <Card className="col-span-2 shadow-sm hover:shadow-md transition-shadow">
      <CardHeader>
        <CardTitle>Invoice Overview</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="h-[300px] flex justify-center items-center">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <div className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{
                  top: 5,
                  right: 30,
                  left: 20,
                  bottom: 25,
                }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "white",
                    border: "1px solid #e0e0e0",
                    borderRadius: "6px",
                    boxShadow: "0 2px 8px rgba(0, 0, 0, 0.15)",
                  }}
                  formatter={(value) => [`$${value}`, ""]}
                />
                <Bar dataKey="paid" name="Paid" fill="#38bdf8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="pending" name="Pending" fill="#60a5fa" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
