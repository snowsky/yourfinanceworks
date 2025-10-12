import React from 'react';
import { ReminderList } from '@/components/reminders';
import { AppLayout } from '@/components/layout/AppLayout';

export default function RemindersPage() {
  return (
    <AppLayout>
      <ReminderList />
    </AppLayout>
  );
}
