import React, { useState, useEffect } from "react";
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
        prepareChartData(data.items);
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
    
    // Group invoices by currency and month
    const chartDataByCurrency = new Map<string, Map<string, { paid: number; pending: number; partiallyPaid: number }>>();

    // Initialize chart data for the last 6 months for each currency
    const months = [];
    const today = new Date();
    
    for (let i = 0; i < 6; i++) {
      // Calculate target month and year more reliably
      let targetMonth = today.getMonth() - 5 + i;
      let targetYear = today.getFullYear();
      
      // Handle year boundary crossing
      while (targetMonth < 0) {
        targetMonth += 12;
        targetYear -= 1;
      }
      
      // Create date with first day of target month to avoid day overflow issues
      const month = new Date(targetYear, targetMonth, 1);
      const monthName = month.toLocaleString('default', { month: 'short' });
      const year = month.getFullYear().toString().slice(2);
      const label = `${monthName} '${year}`;
      months.push(label);
    }
    


    // Process invoices and group by currency
    invoiceData.forEach(invoice => {
      const currency = invoice.currency || 'USD';
      const invoiceDate = new Date(invoice.date || invoice.created_at);
      if (isNaN(invoiceDate.getTime())) return;

      const month = new Date(invoiceDate.getFullYear(), invoiceDate.getMonth(), 1);
      const monthName = month.toLocaleString('default', { month: 'short' });
      const year = month.getFullYear().toString().slice(2);
      const label = `${monthName} '${year}`;

      if (!chartDataByCurrency.has(currency)) {
        chartDataByCurrency.set(currency, new Map());
        // Initialize all months for this currency
        months.forEach(monthLabel => {
          chartDataByCurrency.get(currency)!.set(monthLabel, { paid: 0, pending: 0, partiallyPaid: 0 });
        });
      }

      const currencyData = chartDataByCurrency.get(currency)!;
      if (currencyData.has(label)) {
        const currentData = currencyData.get(label)!;
        if (invoice.status === 'paid') {
          currentData.paid += invoice.amount;
        } else if (invoice.status === 'partially_paid') {
          currentData.partiallyPaid += (invoice.paid_amount || 0);
          currentData.pending += (invoice.amount - (invoice.paid_amount || 0));
        } else if (invoice.status === 'pending' || invoice.status === 'overdue') {
          currentData.pending += invoice.amount;
        }
        currencyData.set(label, currentData);
      }
    });

    // Convert to chart data format with currency information
    const finalChartData = months.map(monthName => {
      const monthData: any = { name: monthName };
      
      chartDataByCurrency.forEach((currencyData, currency) => {
        const data = currencyData.get(monthName) || { paid: 0, pending: 0, partiallyPaid: 0 };
        monthData[`paid_${currency}`] = parseFloat(data.paid.toFixed(2));
        monthData[`pending_${currency}`] = parseFloat(data.pending.toFixed(2));
        monthData[`partiallyPaid_${currency}`] = parseFloat(data.partiallyPaid.toFixed(2));
      });
      
      return monthData;
    });
    
    setChartData(finalChartData);
  };

  return (
    <div className="w-full h-full flex flex-col">
      {loading ? (
        <div className="flex-1 flex justify-center items-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="flex-1 min-h-0">
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
                <YAxis 
                  tick={{ fontSize: 12 }} 
                  tickFormatter={(value) => {
                    // Format Y-axis values with currency symbol
                    const symbols: { [key: string]: string } = {
                      'USD': '$',
                      'EUR': '€',
                      'GBP': '£',
                      'CAD': 'C$',
                      'AUD': 'A$',
                      'JPY': '¥',
                      'CHF': 'CHF',
                      'CNY': '¥',
                      'INR': '₹',
                      'BRL': 'R$',
                      'BTC': '₿',
                      'ETH': 'Ξ',
                      'XRP': 'XRP',
                      'SOL': '◎'
                    };
                    
                    // Try to determine the primary currency from the data
                    const primaryCurrency = chartData.length > 0 ? 
                      Object.keys(chartData[0]).find(key => key.startsWith('paid_') || key.startsWith('pending_'))?.split('_')[1] || 'USD' : 'USD';
                    
                    const symbol = symbols[primaryCurrency.toUpperCase()] || primaryCurrency;
                    return `${symbol}${Number(value).toLocaleString()}`;
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "white",
                    border: "1px solid #e0e0e0",
                    borderRadius: "6px",
                    boxShadow: "0 2px 8px rgba(0, 0, 0, 0.15)",
                  }}
                  formatter={(value, name, props) => {
                    // Extract currency from dataKey (e.g., "paid_USD" -> "USD")
                    const dataKey = props.dataKey as string;
                    const currency = dataKey.split('_')[1] || 'USD';
                    const category = dataKey.split('_')[0];
                    
                  let categoryName = '';
                    if (category === 'paid') {
                    categoryName = 'Paid';
                    } else if (category === 'partiallyPaid') {
                    categoryName = 'Partially Paid';
                    } else if (category === 'pending') {
                    categoryName = 'Pending';
                  } else {
                    categoryName = name; // Fallback
                  }
                    
                    // Format currency with symbol
                    const symbols: { [key: string]: string } = {
                      'USD': '$',
                      'EUR': '€',
                      'GBP': '£',
                      'CAD': 'C$',
                      'AUD': 'A$',
                      'JPY': '¥',
                      'CHF': 'CHF',
                      'CNY': '¥',
                      'INR': '₹',
                      'BRL': 'R$',
                      'BTC': '₿',
                      'ETH': 'Ξ',
                      'XRP': 'XRP',
                      'SOL': '◎'
                    };
                    
                    const symbol = symbols[currency.toUpperCase()] || currency;
                    const formattedValue = `${symbol}${Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
                    
                    return [formattedValue, categoryName];
                }}
                />
                {Array.from(new Set((chartData || []).flatMap(item => 
                  Object.keys(item || {}).filter(key => key.startsWith('paid_') || key.startsWith('pending_') || key.startsWith('partiallyPaid_'))
                    .map(key => key.split('_')[1])
                ))).map((currency, currencyIndex) => {
                  // Color palette for different currencies
                  const currencyColors = {
                    // Traditional currencies
                    'USD': { paid: '#10B981', partiallyPaid: '#F59E0B', pending: '#3B82F6' },
                    'EUR': { paid: '#059669', partiallyPaid: '#D97706', pending: '#2563EB' },
                    'GBP': { paid: '#047857', partiallyPaid: '#B45309', pending: '#1D4ED8' },
                    'CAD': { paid: '#065F46', partiallyPaid: '#92400E', pending: '#1E40AF' },
                    'AUD': { paid: '#064E3B', partiallyPaid: '#78350F', pending: '#1E3A8A' },
                    'JPY': { paid: '#022C22', partiallyPaid: '#451A03', pending: '#1E293B' },
                    'CHF': { paid: '#0F766E', partiallyPaid: '#92400E', pending: '#1E40AF' },
                    'CNY': { paid: '#134E4A', partiallyPaid: '#78350F', pending: '#1E3A8A' },
                    'INR': { paid: '#115E59', partiallyPaid: '#92400E', pending: '#1E40AF' },
                    'BRL': { paid: '#164E63', partiallyPaid: '#92400E', pending: '#1E40AF' },
                    // Cryptocurrencies
                    'BTC': { paid: '#F59E0B', partiallyPaid: '#F97316', pending: '#EF4444' },
                    'ETH': { paid: '#8B5CF6', partiallyPaid: '#A855F7', pending: '#C084FC' },
                    'XRP': { paid: '#06B6D4', partiallyPaid: '#0891B2', pending: '#0E7490' },
                    'SOL': { paid: '#84CC16', partiallyPaid: '#65A30D', pending: '#4D7C0F' },
                    // Default colors for unknown currencies
                    'default': { paid: '#10B981', partiallyPaid: '#F59E0B', pending: '#3B82F6' }
                  };
                  
                  const colors = currencyColors[currency as keyof typeof currencyColors] || currencyColors.default;
                  
                  return (
                    <React.Fragment key={currency}>
                      <Bar 
                        dataKey={`paid_${currency}`} 
                        name={`Paid (${currency})`} 
                        fill={colors.paid}
                        radius={[4, 4, 0, 0]} 
                        stackId={`stack_${currency}`} 
                      />
                      <Bar 
                        dataKey={`partiallyPaid_${currency}`} 
                        name={`Partially Paid (${currency})`} 
                        fill={colors.partiallyPaid}
                        radius={[4, 4, 0, 0]} 
                        stackId={`stack_${currency}`} 
                      />
                      <Bar 
                        dataKey={`pending_${currency}`} 
                        name={`Pending (${currency})`} 
                        fill={colors.pending}
                        radius={[4, 4, 0, 0]} 
                        stackId={`stack_${currency}`} 
                      />
                    </React.Fragment>
                  );
                })}
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
    </div>
  );
}
