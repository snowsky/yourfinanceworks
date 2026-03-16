import { invoiceApi } from './invoices';
import { clientApi } from './clients';
import { expenseApi } from './expenses';
import { approvalApi } from './approvals';

// Activity API methods
export interface ActivityItem {
  id: string;
  type: 'invoice' | 'client' | 'inventory' | 'approval' | 'reminder' | 'expense' | 'report';
  title: string;
  description: string;
  timestamp: string;
  status?: string;
  amount?: number;
  currency?: string;
  link?: string;
  user_id?: number;
  entity_id?: string;
}

export const activityApi = {
  // Get recent activities across all modules
  getRecentActivities: async (limit = 10): Promise<ActivityItem[]> => {
    try {
      // This would be implemented as a backend endpoint that aggregates activities
      // For now, we'll fetch from multiple endpoints and combine them
      const activities: ActivityItem[] = [];

      // Fetch recent invoices
      try {
        const data = await invoiceApi.getInvoices();
        const invoices = data.items;
        const recentInvoices = invoices
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 3)
          .map(invoice => ({
            id: `invoice-${invoice.id}`,
            type: 'invoice' as const,
            title: `Invoice ${invoice.number} ${invoice.status === 'draft' ? 'created' : invoice.status}`,
            description: `Invoice for ${invoice.client_name || 'client'}`,
            timestamp: invoice.created_at,
            status: invoice.status,
            amount: invoice.amount,
            currency: invoice.currency,
            link: `/invoices/${invoice.id}`
          }));
        activities.push(...recentInvoices);
      } catch (error) {
        console.warn('Failed to fetch recent invoices for activity feed:', error);
      }

      // Fetch recent clients
      try {
        const data = await clientApi.getClients(0, 10);
        const clients = data.items;
        const recentClients = clients
          .sort((a, b) => {
            const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
            const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
            return dateB - dateA;
          })
          .slice(0, 2)
          .map(client => ({
            id: `client-${client.id}`,
            type: 'client' as const,
            title: 'New client added',
            description: `${client.name} joined as a client`,
            timestamp: client.created_at,
            link: `/clients/${client.id}`
          }));
        activities.push(...recentClients);
      } catch (error) {
        console.warn('Failed to fetch recent clients for activity feed:', error);
      }

      // Fetch recent expenses
      try {
        const expenses = await expenseApi.getExpenses();
        const recentExpenses = expenses
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
          .slice(0, 2)
          .map(expense => ({
            id: `expense-${expense.id}`,
            type: 'expense' as const,
            title: `Expense ${(expense as any).approval_status || 'submitted'}`,
            description: (expense as any).description || expense.category || 'Business expense',
            timestamp: expense.created_at,
            status: (expense as any).approval_status,
            amount: expense.amount,
            currency: expense.currency,
            link: `/expenses/${expense.id}`
          }));
        activities.push(...recentExpenses);
      } catch (error) {
        console.warn('Failed to fetch recent expenses for activity feed:', error);
      }

      // Fetch recent approvals
      try {
        const approvalsResponse = await approvalApi.getPendingApprovals();
        const approvals = Array.isArray(approvalsResponse) ? approvalsResponse : approvalsResponse.approvals || [];
        const recentApprovals = approvals
          .sort((a, b) => new Date(b.submitted_at).getTime() - new Date(a.submitted_at).getTime())
          .slice(0, 2)
          .map(approval => ({
            id: `approval-${approval.id}`,
            type: 'approval' as const,
            title: `${approval.expense_type || 'Expense'} approval ${approval.status}`,
            description: approval.description || 'Expense approval',
            timestamp: approval.submitted_at,
            status: approval.status,
            amount: approval.amount,
            currency: approval.currency,
            link: `/approvals/${approval.id}`
          }));
        activities.push(...recentApprovals);
      } catch (error) {
        console.warn('Failed to fetch recent approvals for activity feed:', error);
      }

      // Sort all activities by timestamp and limit
      return activities
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, limit);

    } catch (error) {
      console.error('Failed to fetch recent activities:', error);
      throw error;
    }
  },

  // Get activities for a specific type
  getActivitiesByType: async (type: ActivityItem['type'], limit = 10): Promise<ActivityItem[]> => {
    const allActivities = await activityApi.getRecentActivities(50);
    return allActivities.filter(activity => activity.type === type).slice(0, limit);
  },

  // Get activities for a specific date range
  getActivitiesByDateRange: async (startDate: string, endDate: string): Promise<ActivityItem[]> => {
    const allActivities = await activityApi.getRecentActivities(100);
    return allActivities.filter(activity => {
      const activityDate = new Date(activity.timestamp);
      return activityDate >= new Date(startDate) && activityDate <= new Date(endDate);
    });
  }
};
