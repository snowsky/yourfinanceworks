# Notification System Update - Ephemeral Notifications

## Problem

After rebuilding the application, users were seeing old notifications that persisted from previous versions. This happened because:

1. **Frontend notifications** were stored in `localStorage` with key `'ai_notifications'`
2. `localStorage` persists across browser sessions, app rebuilds, and deployments
3. Old notification formats or stale data could cause issues
4. **A rebuild doesn't clear browser localStorage** - it only updates the code

## Solution

**Removed localStorage persistence entirely** - notifications are now ephemeral (in-memory only).

### Why This Is Better

1. **Notifications should be ephemeral** - They're meant to show real-time events, not historical data
2. **No stale data** - Fresh start on every page load
3. **Simpler code** - No serialization/deserialization logic
4. **Better UX** - Users see only current, relevant notifications
5. **No version management needed** - No complex versioning system required

### How It Works

**File: `ui/src/hooks/useNotifications.ts`**

```typescript
export function useNotifications() {
  // Notifications are now ephemeral - they don't persist across page reloads
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Clean up any old localStorage data from previous versions
  useEffect(() => {
    localStorage.removeItem('ai_notifications');
    localStorage.removeItem('ai_notifications_version');
  }, []);
  
  // ... rest of the hook
}
```

### Behavior

- **On page load**: Notifications start empty
- **During session**: Notifications accumulate in memory
- **On page reload**: Notifications are cleared (fresh start)
- **On rebuild**: Old localStorage data is automatically cleaned up

### Migration

The hook automatically cleans up old localStorage data on first load, so users upgrading from the old version will have their persisted notifications removed.

## Two Notification Systems

The application has **two separate notification systems**:

### 1. Backend OCR Notifications (In-Memory)
- **Location**: `api/utils/ocr_notifications.py`
- **Storage**: In-memory dictionary
- **Lifetime**: Until server restart or manual clear
- **Purpose**: Real-time OCR processing status
- **Clear function**: `clear_all_ocr_notifications()`

```python
# Backend - clears in-memory OCR notifications
def clear_all_ocr_notifications() -> int:
    return ocr_notification_manager.clear_all_notifications()
```

### 2. Frontend UI Notifications (localStorage)
- **Location**: `ui/src/hooks/useNotifications.ts`
- **Storage**: Browser localStorage
- **Lifetime**: Persists across sessions until manually cleared or version changes
- **Purpose**: User-facing notification bell
- **Clear function**: `clearAll()` from hook

```typescript
// Frontend - clears localStorage notifications
const { clearAll } = useNotifications();
clearAll(); // Clears all notifications
```

## Benefits

1. **Automatic cleanup** - Old notifications cleared on version change
2. **No manual intervention** - Users don't need to clear cache
3. **Backward compatible** - Gracefully handles version upgrades
4. **Error resilient** - Corrupted data automatically cleared
5. **Developer friendly** - Simple version increment to trigger cleanup

## Manual Clear Options

### For Users
Users can clear notifications manually:
1. Click the notification bell
2. Click "Clear All" button
3. Reload the page (notifications are ephemeral)

### For Backend OCR Notifications
```python
# In Python console or script
from utils.ocr_notifications import clear_all_ocr_notifications
cleared_count = clear_all_ocr_notifications()
print(f"Cleared {cleared_count} OCR notifications")
```

## When to Use Persistent Notifications

If you need notifications to persist across page reloads, consider:

1. **Database storage** - Store in backend database
2. **Server-sent events** - Real-time updates from server
3. **Polling** - Fetch notifications from API on mount
4. **Session storage** - Persist only for current tab session

## Testing

To test the notification system:

```typescript
// 1. Add some notifications
const { addNotification } = useNotifications();
addNotification('info', 'Test', 'Test notification');

// 2. Verify they appear in the UI
// 3. Reload page - notifications should be cleared
// 4. Old localStorage data should be removed
```

## Notes

- Notifications are now ephemeral (in-memory only)
- Page reload clears all notifications
- Old localStorage data is automatically cleaned up on first load
- Backend OCR notifications are independent and stored in-memory on the server
- For persistent notifications, use the backend database instead
