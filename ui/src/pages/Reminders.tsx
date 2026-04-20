import React from 'react';
import { ReminderList } from '@/components/reminders';

export default function RemindersPage() {
  return (
    <>
      <div className="h-full space-y-8 fade-in dashboard-highlight-mode dashboard-shell">
        <ReminderList />
      </div>
    </>
  );
}
