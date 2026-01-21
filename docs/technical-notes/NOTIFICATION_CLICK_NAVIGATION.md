# Notification Click-to-Navigate Enhancement

## Overview
Enhanced the notification system to allow users to click on notifications and navigate directly to the relevant page (e.g., expense view page for approval notifications).

## Implementation

### Backend Changes
**File:** `api/commercial/workflows/approvals/router.py`

Updated notification creation to include expense_id in the subject line:
- **Approval Request:** `"Expense Approval Request #123"`
- **Approved:** `"Expense Approved #123"`
- **Rejected:** `"Expense Rejected #123"`

This allows the frontend to extract the expense_id and navigate to the correct page.

### Frontend Changes
**File:** `ui/src/components/reminders/InAppNotifications.tsx`

Added functionality to:
1. **Extract expense_id** from notification subject using regex pattern `/#(\d+)/`
2. **Handle notification clicks** with `handleNotificationClick()` function
3. **Navigate to expense view** page at `/expenses/view/{expense_id}`
4. **Mark notification as read** automatically on click
5. **Show visual badges** for different notification types:
   - 🟠 Orange "Approval Needed" badge for pending approvals
   - 🟢 Green "Approved" badge for approved expenses
   - 🔴 Red "Rejected" badge for rejected expenses

## Supported Notification Types

### Clickable Notifications:
- ✅ `expense_approval` → Navigate to expense view page
- ✅ `expense_approved` → Navigate to expense view page
- ✅ `expense_rejected` → Navigate to expense view page
- ✅ `join_request` → Navigate to organization join requests page (existing)

### Non-Clickable Notifications:
- Reminder notifications (due, overdue, upcoming, assigned)
- These show reminder details but don't navigate away

## User Experience

### Before:
1. User receives notification
2. Clicks notification → Nothing happens
3. User must manually navigate to expenses page
4. User must search for the specific expense

### After:
1. User receives notification
2. Clicks notification → Automatically navigated to expense view page ✨
3. Notification marked as read
4. User can immediately review and take action

## Technical Details

### Expense ID Extraction
```typescript
const extractExpenseId = (subject?: string): number | null => {
  if (!subject) return null;
  const match = subject.match(/#(\d+)/);
  return match ? parseInt(match[1]) : null;
};
```

### Click Handler
```typescript
const handleNotificationClick = (notification: InAppNotification) => {
  const { notification_type, subject } = notification;
  
  if (notification_type === 'expense_approval' || 
      notification_type === 'expense_approved' || 
      notification_type === 'expense_rejected') {
    const expenseId = extractExpenseId(subject);
    if (expenseId) {
      markAsRead(notification.id);
      setOpen(false);
      window.location.href = `/expenses/view/${expenseId}`;
    }
  }
};
```

### Visual Styling
- Clickable notifications show `cursor-pointer` on hover
- Unread notifications have blue background
- Expense notifications have colored badges for quick identification
- Hover effect provides visual feedback

## Benefits

1. **Faster Navigation:** One click to reach the relevant page
2. **Better UX:** Intuitive and expected behavior
3. **Reduced Friction:** No manual searching required
4. **Clear Visual Cues:** Badges indicate notification type and status
5. **Automatic Read Status:** Notifications marked as read on click
6. **Extensible Pattern:** Easy to add more clickable notification types

## Future Extensions

This pattern can be extended to other notification types:
- Invoice notifications → Navigate to invoice view
- Payment notifications → Navigate to payment details
- Report notifications → Navigate to report page
- Task notifications → Navigate to task details

## Testing

To test the feature:
1. Submit an expense for approval
2. Log in as the approver
3. Click the bell icon to open notifications
4. Click on the "Expense Approval Request" notification
5. Verify navigation to expense view page
6. Verify notification is marked as read
7. Test with approved/rejected notifications as well
