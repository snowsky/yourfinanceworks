"""
Reminder and notification-related tools mixin.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ListRemindersArgs(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    status: Optional[List[str]] = Field(default=None, description="Filter by status")
    priority: Optional[List[str]] = Field(default=None, description="Filter by priority")
    search: Optional[str] = Field(default=None, description="Search in title and description")


class GetReminderArgs(BaseModel):
    reminder_id: int = Field(description="ID of the reminder")


class CreateReminderArgs(BaseModel):
    title: str = Field(description="Reminder title")
    description: Optional[str] = Field(default=None, description="Reminder description")
    due_date: str = Field(description="Due date (ISO format)")
    assigned_to_id: int = Field(description="User ID to assign to")
    priority: str = Field(default="medium", description="Priority level")
    recurrence_pattern: str = Field(default="none", description="Recurrence pattern")
    tags: Optional[List[str]] = Field(default=None, description="Tags")


class UpdateReminderArgs(BaseModel):
    reminder_id: int = Field(description="ID of the reminder")
    title: Optional[str] = Field(default=None, description="New title")
    description: Optional[str] = Field(default=None, description="New description")
    due_date: Optional[str] = Field(default=None, description="New due date")
    priority: Optional[str] = Field(default=None, description="New priority")


class UpdateReminderStatusArgs(BaseModel):
    reminder_id: int = Field(description="ID of the reminder")
    status: str = Field(description="New status")
    completion_notes: Optional[str] = Field(default=None, description="Completion notes")
    snoozed_until: Optional[str] = Field(default=None, description="Snooze until date")


class UnsnoozeReminderArgs(BaseModel):
    reminder_id: int = Field(description="ID of the reminder to unsnooze")


class DeleteReminderArgs(BaseModel):
    reminder_id: int = Field(description="ID of the reminder to delete")


class BulkUpdateRemindersArgs(BaseModel):
    reminder_ids: List[int] = Field(description="List of reminder IDs")
    status: Optional[str] = Field(default=None, description="New status")
    priority: Optional[str] = Field(default=None, description="New priority")


class GetReminderNotificationsArgs(BaseModel):
    reminder_id: int = Field(description="ID of the reminder")


class GetDueTodayRemindersArgs(BaseModel):
    pass  # No arguments needed


class GetOverdueRemindersArgs(BaseModel):
    pass  # No arguments needed


class GetUnreadNotificationCountArgs(BaseModel):
    pass  # No arguments needed


class GetRecentNotificationsArgs(BaseModel):
    limit: int = Field(default=20, ge=1, le=100, description="Maximum notifications")


class MarkNotificationReadArgs(BaseModel):
    notification_id: int = Field(description="ID of the notification")


class MarkAllNotificationsReadArgs(BaseModel):
    pass  # No arguments needed


class DismissNotificationArgs(BaseModel):
    notification_id: int = Field(description="ID of the notification")


class ReminderToolsMixin:
    # === Reminder Management Tools ===

    async def list_reminders(self, page: int = 1, per_page: int = 20, status: Optional[List[str]] = None, priority: Optional[List[str]] = None, search: Optional[str] = None) -> Dict[str, Any]:
        """List reminders with filtering and pagination"""
        try:
            params = {"page": page, "per_page": per_page}
            if status:
                params["status"] = status
            if priority:
                params["priority"] = priority
            if search:
                params["search"] = search

            response = await self.api_client._make_request("GET", "/reminders", params=params)
            return {
                "success": True,
                "data": response.get("items", []),
                "total": response.get("total", 0),
                "page": response.get("page", page),
                "pages": response.get("pages", 1),
                "message": f"Found {response.get('total', 0)} reminders"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to list reminders: {e}"}

    async def get_reminder(self, reminder_id: int) -> Dict[str, Any]:
        """Get a specific reminder"""
        try:
            response = await self.api_client._make_request("GET", f"/reminders/{reminder_id}")
            return {"success": True, "data": response, "message": "Reminder retrieved successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get reminder: {e}"}

    async def create_reminder(self, title: str, due_date: str, assigned_to_id: int, description: Optional[str] = None, priority: str = "medium", recurrence_pattern: str = "none", tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new reminder"""
        try:
            payload = {
                "title": title,
                "due_date": due_date,
                "assigned_to_id": assigned_to_id,
                "priority": priority,
                "recurrence_pattern": recurrence_pattern
            }
            if description:
                payload["description"] = description
            if tags:
                payload["tags"] = tags

            response = await self.api_client._make_request("POST", "/reminders", json=payload)
            return {"success": True, "data": response, "message": "Reminder created successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to create reminder: {e}"}

    async def update_reminder(self, reminder_id: int, title: Optional[str] = None, description: Optional[str] = None, due_date: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
        """Update a reminder"""
        try:
            payload = {}
            if title:
                payload["title"] = title
            if description:
                payload["description"] = description
            if due_date:
                payload["due_date"] = due_date
            if priority:
                payload["priority"] = priority

            response = await self.api_client._make_request("PUT", f"/reminders/{reminder_id}", json=payload)
            return {"success": True, "data": response, "message": "Reminder updated successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to update reminder: {e}"}

    async def update_reminder_status(self, reminder_id: int, status: str, completion_notes: Optional[str] = None, snoozed_until: Optional[str] = None) -> Dict[str, Any]:
        """Update reminder status"""
        try:
            payload = {"status": status}
            if completion_notes:
                payload["completion_notes"] = completion_notes
            if snoozed_until:
                payload["snoozed_until"] = snoozed_until

            response = await self.api_client._make_request("PATCH", f"/reminders/{reminder_id}/status", json=payload)
            return {"success": True, "data": response, "message": f"Reminder status updated to {status}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to update reminder status: {e}"}

    async def unsnooze_reminder(self, reminder_id: int) -> Dict[str, Any]:
        """Unsnooze a reminder"""
        try:
            response = await self.api_client._make_request("POST", f"/reminders/{reminder_id}/unsnooze")
            return {"success": True, "data": response, "message": "Reminder unsnoozed successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to unsnooze reminder: {e}"}

    async def delete_reminder(self, reminder_id: int) -> Dict[str, Any]:
        """Delete a reminder"""
        try:
            await self.api_client._make_request("DELETE", f"/reminders/{reminder_id}")
            return {"success": True, "message": "Reminder deleted successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete reminder: {e}"}

    async def bulk_update_reminders(self, reminder_ids: List[int], status: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
        """Bulk update multiple reminders"""
        try:
            payload = {"reminder_ids": reminder_ids}
            if status:
                payload["status"] = status
            if priority:
                payload["priority"] = priority

            response = await self.api_client._make_request("POST", "/reminders/bulk-update", json=payload)
            return {
                "success": True,
                "data": response,
                "updated_count": response.get("updated_count", 0),
                "message": f"Updated {response.get('updated_count', 0)} reminders"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to bulk update reminders: {e}"}

    async def get_reminder_notifications(self, reminder_id: int) -> Dict[str, Any]:
        """Get notifications for a reminder"""
        try:
            response = await self.api_client._make_request("GET", f"/reminders/{reminder_id}/notifications")
            return {"success": True, "data": response, "count": len(response), "message": f"Found {len(response)} notifications"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get reminder notifications: {e}"}

    async def get_due_today_reminders(self) -> Dict[str, Any]:
        """Get reminders due today"""
        try:
            response = await self.api_client._make_request("GET", "/reminders/due/today")
            return {"success": True, "data": response, "count": len(response), "message": f"Found {len(response)} reminders due today"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get due today reminders: {e}"}

    async def get_overdue_reminders(self) -> Dict[str, Any]:
        """Get overdue reminders"""
        try:
            response = await self.api_client._make_request("GET", "/reminders/overdue")
            return {"success": True, "data": response, "count": len(response), "message": f"Found {len(response)} overdue reminders"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get overdue reminders: {e}"}

    async def get_unread_notification_count(self) -> Dict[str, Any]:
        """Get count of unread notifications"""
        try:
            response = await self.api_client._make_request("GET", "/reminders/notifications/unread-count")
            return {"success": True, "data": response, "count": response.get("count", 0), "message": f"{response.get('count', 0)} unread notifications"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get unread notification count: {e}"}

    async def get_recent_notifications(self, limit: int = 20) -> Dict[str, Any]:
        """Get recent notifications"""
        try:
            params = {"limit": limit}
            response = await self.api_client._make_request("GET", "/reminders/notifications/recent", params=params)
            items = response.get("items", [])
            return {"success": True, "data": items, "count": len(items), "message": f"Found {len(items)} recent notifications"}
        except Exception as e:
            return {"success": False, "error": f"Failed to get recent notifications: {e}"}

    async def mark_notification_read(self, notification_id: int) -> Dict[str, Any]:
        """Mark a notification as read"""
        try:
            response = await self.api_client._make_request("POST", f"/reminders/notifications/{notification_id}/read")
            return {"success": True, "data": response, "message": "Notification marked as read"}
        except Exception as e:
            return {"success": False, "error": f"Failed to mark notification as read: {e}"}

    async def mark_all_notifications_read(self) -> Dict[str, Any]:
        """Mark all notifications as read"""
        try:
            response = await self.api_client._make_request("POST", "/reminders/notifications/mark-all-read")
            return {"success": True, "data": response, "message": "All notifications marked as read"}
        except Exception as e:
            return {"success": False, "error": f"Failed to mark all notifications as read: {e}"}

    async def dismiss_notification(self, notification_id: int) -> Dict[str, Any]:
        """Dismiss a notification"""
        try:
            await self.api_client._make_request("DELETE", f"/reminders/notifications/{notification_id}")
            return {"success": True, "message": "Notification dismissed successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to dismiss notification: {e}"}
