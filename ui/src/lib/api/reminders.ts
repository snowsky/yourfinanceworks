import { apiRequest } from './_base';

// Reminder API methods
export const reminderApi = {
  // Reminders CRUD
  getReminders: async (params: {
    page?: number;
    per_page?: number;
    status?: string[];
    priority?: string[];
    assigned_to_id?: number;
    created_by_id?: number;
    due_date_from?: string;
    due_date_to?: string;
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  } = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          value.forEach(v => searchParams.append(key, v));
        } else {
          searchParams.set(key, String(value));
        }
      }
    });
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return apiRequest<any>(`/reminders/${query}`);
  },

  getReminder: async (id: number) => {
    return apiRequest<any>(`/reminders/${id}`);
  },

  createReminder: async (reminder: any) => {
    return apiRequest<any>('/reminders/', {
      method: 'POST',
      body: JSON.stringify(reminder),
    });
  },

  updateReminder: async (id: number, reminder: any) => {
    return apiRequest<any>(`/reminders/${id}`, {
      method: 'PUT',
      body: JSON.stringify(reminder),
    });
  },

  updateReminderStatus: async (id: number, statusData: any) => {
    return apiRequest<any>(`/reminders/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify(statusData),
    });
  },

  deleteReminder: async (id: number) => {
    return apiRequest(`/reminders/${id}`, {
      method: 'DELETE',
    });
  },

  bulkUpdateReminders: async (data: any) => {
    return apiRequest<any>('/reminders/bulk-update', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  bulkDeleteReminders: async (reminderIds: number[]) => {
    return apiRequest<any>('/reminders/bulk-delete', {
      method: 'DELETE',
      body: JSON.stringify(reminderIds),
    });
  },

  getDueToday: async () => {
    return apiRequest<any>('/reminders/due/today');
  },

  getOverdue: async () => {
    return apiRequest<any>('/reminders/overdue/');
  },

  unsnoozeReminder: async (id: number) => {
    return apiRequest<any>(`/reminders/${id}/unsnooze`, {
      method: 'POST',
    });
  },

  reorderReminders: async (reminderIds: number[]) => {
    return apiRequest<any>('/reminders/reorder', {
      method: 'POST',
      body: JSON.stringify({ reminder_ids: reminderIds }),
    });
  },

  toggleReminderPin: async (id: number) => {
    return apiRequest<any>(`/reminders/${id}/toggle-pin`, {
      method: 'POST',
    });
  },

  // Notification methods
  getUnreadNotificationCount: async () => {
    return apiRequest<{ count: number }>('/reminders/notifications/unread-count');
  },

  getRecentNotifications: async (limit: number = 20) => {
    return apiRequest<any>(`/reminders/notifications/recent?limit=${limit}`);
  },

  markNotificationAsRead: async (notificationId: number) => {
    return apiRequest(`/reminders/notifications/${notificationId}/read`, {
      method: 'POST',
    });
  },

  markAllNotificationsAsRead: async () => {
    return apiRequest('/reminders/notifications/mark-all-read', {
      method: 'POST',
    });
  },

  dismissNotification: async (notificationId: number) => {
    return apiRequest(`/reminders/notifications/${notificationId}`, {
      method: 'DELETE',
    });
  },

  getReminderNotifications: async (reminderId: number) => {
    return apiRequest<any>(`/reminders/${reminderId}/notifications`);
  },
};
