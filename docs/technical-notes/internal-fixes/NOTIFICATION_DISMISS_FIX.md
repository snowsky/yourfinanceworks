# Notification Dismiss Fix

## Issue
When users clicked the X button to dismiss a notification, it would disappear from the UI temporarily, but reappear after a page refresh. This was because the dismiss endpoint wasn't actually deleting the notification from the database.

## Root Cause
The `dismiss_notification` endpoint in `api/core/routers/reminders.py` was returning success without actually deleting the notification:

```python
# Old code - didn't actually delete
def dismiss_notification(...):
    notification = db.query(ReminderNotification).filter(...).first()
    if not notification:
        raise HTTPException(...)
    
    # Just returned without doing anything!
    return
```

The comment even said "The frontend will handle removing it from the UI" - but this only worked until the page refreshed and reloaded all notifications from the database.

## Solution
Updated the endpoint to actually delete the notification from the database:

```python
# New code - actually deletes
def dismiss_notification(...):
    notification = db.query(ReminderNotification).filter(...).first()
    if not notification:
        raise HTTPException(...)
    
    # Delete the notification from the database
    db.delete(notification)
    db.commit()
    
    return
```

## Impact
- ✅ Dismissed notifications stay dismissed after page refresh
- ✅ Dismissed notifications don't reappear in the notification list
- ✅ Unread count decreases correctly when notifications are dismissed
- ✅ No breaking changes - frontend code works as-is

## Technical Details

### Database Operation
- Uses SQLAlchemy's `db.delete()` to remove the notification record
- Commits the transaction with `db.commit()`
- Returns HTTP 204 No Content on success

### Security
- Endpoint verifies the notification belongs to the current user
- Only the notification owner can dismiss their own notifications
- Returns 404 if notification not found or doesn't belong to user

### Frontend Behavior
The frontend already had the correct implementation:
1. User clicks X button
2. Calls `dismissNotification(notificationId)` API
3. Removes notification from local state
4. Decrements unread count if notification was unread

Now the backend properly persists this dismissal.

## Alternative Approaches Considered

### Soft Delete (is_dismissed flag)
Could add an `is_dismissed` boolean field to track dismissed notifications:
- **Pros:** Keeps audit trail, can "undo" dismissals
- **Cons:** Requires database migration, more complex queries
- **Decision:** Not needed for MVP - hard delete is simpler

### Expiration-based Cleanup
Could auto-delete old notifications after X days:
- **Pros:** Keeps database clean automatically
- **Cons:** Adds complexity, may delete notifications users want to keep
- **Decision:** Can add later if needed

## Testing

To verify the fix:
1. Open notification dropdown
2. Click X to dismiss a notification
3. Refresh the page
4. Verify the notification doesn't reappear ✅
5. Check that unread count is correct ✅

## Related Files
- `api/core/routers/reminders.py` - Dismiss endpoint implementation
- `ui/src/components/reminders/InAppNotifications.tsx` - Frontend dismiss handler
- `api/core/models/models_per_tenant.py` - ReminderNotification model
