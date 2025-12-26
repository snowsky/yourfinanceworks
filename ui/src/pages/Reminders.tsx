import React from 'react';
import { ReminderList } from '@/components/reminders';

export default function RemindersPage() {
  return (
    <>
      <div className="h-full p-8">
        <ReminderList />
      </div>
    </>
  );
}
