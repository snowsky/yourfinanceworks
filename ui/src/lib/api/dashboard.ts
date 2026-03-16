import { clientApi } from './clients';
import { invoiceApi } from './invoices';
import { paymentApi } from './payments';
import { expenseApi } from './expenses';
import type { DashboardStats } from './invoices';

// Dashboard API
export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    try {
      const [clientsData, invoicesData, payments] = await Promise.all([
        clientApi.getClients(0, 1000), // get more for dashboard
        invoiceApi.getInvoices(undefined, undefined, 0, 1000),
        paymentApi.getPayments(),
      ]);

      const clients = clientsData.items;
      const invoices = invoicesData.items;

      const totalClients = clientsData.total;
      // Group totals by currency
      const totalIncome: Record<string, number> = {};
      const pendingInvoices: Record<string, number> = {};
      const totalExpenses: Record<string, number> = {};

      invoices.forEach(invoice => {
        const currency = invoice.currency || 'USD';

        // Only count income from invoices where the payer is 'Client'
        const payer = (invoice.payer || '').toLowerCase();
        if ((invoice.status === 'paid' || invoice.status === 'partially_paid') && (payer === 'client' || payer === '')) {
          totalIncome[currency] = (totalIncome[currency] || 0) + invoice.paid_amount;
        }
        // Calculate pending amounts for invoices that are not fully paid
        if (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid') {
          const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
          if (outstandingAmount > 0) {
            pendingInvoices[currency] = (pendingInvoices[currency] || 0) + outstandingAmount;
          }
        }
      });

      // Fetch and calculate total expenses
      try {
        const expenses = await expenseApi.getExpenses();
        // Ensure expenses is an array before iterating
        if (Array.isArray(expenses)) {
          expenses.forEach(expense => {
            const currency = expense.currency || 'USD';
            const amount = expense.total_amount || expense.amount || 0;

            totalExpenses[currency] = (totalExpenses[currency] || 0) + amount;
          });
        } else {
          console.warn('Expenses API returned non-array response:', expenses);
        }
      } catch (error) {
        console.error('Failed to fetch expenses for dashboard:', error);
      }

      const invoicesPaid = (invoices || []).filter(invoice => invoice.status === 'paid').length;
      const invoicesPending = (invoices || []).filter(invoice => invoice.status === 'pending').length;
      const invoicesOverdue = (invoices || []).filter(invoice => invoice.status === 'overdue').length;

      // Calculate trends by comparing current month vs previous month
      const now = new Date();
      const currentMonth = now.getMonth();
      const currentYear = now.getFullYear();
      const previousMonth = currentMonth === 0 ? 11 : currentMonth - 1;
      const previousYear = currentMonth === 0 ? currentYear - 1 : currentYear;

      // Helper function to calculate total for a specific month
      const calculateMonthlyTotal = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth &&
              invoiceDate.getFullYear() === targetYear &&
              (invoice.status === 'paid' || invoice.status === 'partially_paid');
          })
          .reduce((sum, invoice) => sum + (invoice.paid_amount || 0), 0);
      };

      // Helper function to calculate pending for a specific month
      const calculateMonthlyPending = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth &&
              invoiceDate.getFullYear() === targetYear &&
              (invoice.status === 'pending' || invoice.status === 'overdue' || invoice.status === 'partially_paid');
          })
          .reduce((sum, invoice) => {
            const outstandingAmount = invoice.amount - (invoice.paid_amount || 0);
            return sum + (outstandingAmount > 0 ? outstandingAmount : 0);
          }, 0);
      };

      // Helper function to calculate client count for a specific month
      const calculateMonthlyClients = (targetMonth: number, targetYear: number) => {
        const clientIds = new Set();
        (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth &&
              invoiceDate.getFullYear() === targetYear;
          })
          .forEach(invoice => clientIds.add(invoice.client_id));
        return clientIds.size;
      };

      // Helper function to calculate overdue count for a specific month
      const calculateMonthlyOverdue = (targetMonth: number, targetYear: number) => {
        return (invoices || [])
          .filter(invoice => {
            const invoiceDate = new Date(invoice.created_at);
            return invoiceDate.getMonth() === targetMonth &&
              invoiceDate.getFullYear() === targetYear &&
              invoice.status === 'overdue';
          }).length;
      };

      // Calculate current and previous month totals
      const currentMonthIncome = calculateMonthlyTotal(currentMonth, currentYear);
      const previousMonthIncome = calculateMonthlyTotal(previousMonth, previousYear);
      const currentMonthPending = calculateMonthlyPending(currentMonth, currentYear);
      const previousMonthPending = calculateMonthlyPending(previousMonth, previousYear);
      const currentMonthClients = calculateMonthlyClients(currentMonth, currentYear);
      const previousMonthClients = calculateMonthlyClients(previousMonth, previousYear);
      const currentMonthOverdue = calculateMonthlyOverdue(currentMonth, currentYear);
      const previousMonthOverdue = calculateMonthlyOverdue(previousMonth, previousYear);


      // Calculate percentage changes
      const calculatePercentageChange = (current: number, previous: number) => {
        if (previous === 0) return current > 0 ? 100 : 0;
        return ((current - previous) / previous) * 100;
      };

      const incomeTrend = calculatePercentageChange(currentMonthIncome, previousMonthIncome);
      const pendingTrend = calculatePercentageChange(currentMonthPending, previousMonthPending);
      const clientsTrend = calculatePercentageChange(currentMonthClients, previousMonthClients);
      const overdueTrend = calculatePercentageChange(currentMonthOverdue, previousMonthOverdue);

      // Calculate real payment trends metrics
      let onTimePaymentRate = 0;
      let averagePaymentTime = 0;
      let overdueRate = 0;

      if (invoices && invoices.length > 0) {
        const paidInvoices = invoices.filter(inv => inv.status === 'paid' || inv.status === 'partially_paid');
        const overdueInvoices = invoices.filter(inv => inv.status === 'overdue');

        // Calculate on-time payment rate
        if (paidInvoices.length > 0) {
          const onTimePayments = paidInvoices.filter(invoice => {
            if (!invoice.due_date || !invoice.updated_at) return false;
            const dueDate = new Date(invoice.due_date);
            const paidDate = new Date(invoice.updated_at);
            return paidDate <= dueDate;
          });
          onTimePaymentRate = Math.round((onTimePayments.length / paidInvoices.length) * 100);
        }

        // Calculate average payment time (in days)
        if (paidInvoices.length > 0) {
          const totalPaymentDays = paidInvoices.reduce((sum, invoice) => {
            if (!invoice.date || !invoice.updated_at) return sum;
            const createdDate = new Date(invoice.date);
            const paidDate = new Date(invoice.updated_at);
            const daysDiff = Math.ceil((paidDate.getTime() - createdDate.getTime()) / (1000 * 60 * 60 * 24));
            return sum + daysDiff;
          }, 0);
          averagePaymentTime = Math.round(totalPaymentDays / paidInvoices.length);
        }

        // Calculate overdue rate
        overdueRate = Math.round((overdueInvoices.length / invoices.length) * 100);
      }

      console.log('Payment trends calculations:', {
        onTimePaymentRate,
        averagePaymentTime,
        overdueRate
      });

      return {
        totalIncome,
        pendingInvoices,
        totalExpenses,
        totalClients,
        invoicesPaid,
        invoicesPending,
        invoicesOverdue,
        paymentTrends: {
          onTimePaymentRate,
          averagePaymentTime,
          overdueRate
        },
        trends: {
          income: { value: Math.round(incomeTrend * 10) / 10, isPositive: incomeTrend >= 0 },
          pending: { value: Math.round(pendingTrend * 10) / 10, isPositive: pendingTrend >= 0 },
          clients: { value: Math.round(clientsTrend * 10) / 10, isPositive: clientsTrend >= 0 },
          overdue: { value: Math.round(overdueTrend * 10) / 10, isPositive: overdueTrend >= 0 }
        }
      };
    } catch (error) {
      console.error('Failed to get dashboard stats:', error);
      return {
        totalIncome: {},
        pendingInvoices: {},
        totalExpenses: {},
        totalClients: 0,
        invoicesPaid: 0,
        invoicesPending: 0,
        invoicesOverdue: 0,
        paymentTrends: {
          onTimePaymentRate: 0,
          averagePaymentTime: 0,
          overdueRate: 0
        },
        trends: {
          income: { value: 0, isPositive: true },
          pending: { value: 0, isPositive: true },
          clients: { value: 0, isPositive: true },
          overdue: { value: 0, isPositive: false }
        }
      };
    }
  }
};
