import React from 'react';
import { ReminderList } from '@/components/reminders';
import { AppLayout } from '@/components/layout/AppLayout';

export default function RemindersPage() {
  return (
    <AppLayout>
      <div className="h-full p-8">
        <ReminderList />
      </div>
    </AppLayout>
  );
}
