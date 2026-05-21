"""Static event metadata for notification rendering.

Pure lookup table mapping notification event types to their display title,
description, and accent color. Split out of :mod:`notification_service` so the
service module doesn't carry a 150-line static dict literal.
"""

from typing import Dict

# Title/description/color for every notification event type the system emits.
EVENT_INFO: Dict[str, Dict[str, str]] = {
    # User events
    'user_created': {
        'title': 'New User Created',
        'description': 'A new user has been added to your organization.',
        'color': '#28a745',
    },
    'user_updated': {
        'title': 'User Updated',
        'description': 'A user\'s information has been updated.',
        'color': '#ffc107',
    },
    'user_deleted': {
        'title': 'User Deleted',
        'description': 'A user has been removed from your organization.',
        'color': '#dc3545',
    },
    'user_login': {
        'title': 'User Login',
        'description': 'A user has logged into the system.',
        'color': '#17a2b8',
    },

    # Client events
    'client_created': {
        'title': 'New Client Added',
        'description': 'A new client has been added to your system.',
        'color': '#28a745',
    },
    'client_updated': {
        'title': 'Client Updated',
        'description': 'A client\'s information has been updated.',
        'color': '#ffc107',
    },
    'client_deleted': {
        'title': 'Client Deleted',
        'description': 'A client has been removed from your system.',
        'color': '#dc3545',
    },

    # Invoice events
    'invoice_created': {
        'title': 'New Invoice Created',
        'description': 'A new invoice has been created.',
        'color': '#28a745',
    },
    'invoice_updated': {
        'title': 'Invoice Updated',
        'description': 'An invoice has been updated.',
        'color': '#ffc107',
    },
    'invoice_deleted': {
        'title': 'Invoice Deleted',
        'description': 'An invoice has been deleted.',
        'color': '#dc3545',
    },
    'invoice_sent': {
        'title': 'Invoice Sent',
        'description': 'An invoice has been sent to a client.',
        'color': '#17a2b8',
    },
    'invoice_paid': {
        'title': 'Invoice Paid',
        'description': 'An invoice has been marked as paid.',
        'color': '#28a745',
    },
    'invoice_overdue': {
        'title': 'Invoice Overdue',
        'description': 'An invoice is now overdue.',
        'color': '#dc3545',
    },

    # Payment events
    'payment_created': {
        'title': 'Payment Recorded',
        'description': 'A new payment has been recorded.',
        'color': '#28a745',
    },
    'payment_updated': {
        'title': 'Payment Updated',
        'description': 'A payment has been updated.',
        'color': '#ffc107',
    },
    'payment_deleted': {
        'title': 'Payment Deleted',
        'description': 'A payment has been deleted.',
        'color': '#dc3545',
    },

    # Settings events
    'settings_updated': {
        'title': 'Settings Updated',
        'description': 'System settings have been updated.',
        'color': '#6f42c1',
    },

    # Approval events
    'expense_submitted_for_approval': {
        'title': 'Expense Submitted for Approval',
        'description': 'An expense has been submitted and requires your approval.',
        'color': '#ffc107',
    },
    'expense_approved': {
        'title': 'Expense Approved',
        'description': 'Your expense has been approved.',
        'color': '#28a745',
    },
    'expense_rejected': {
        'title': 'Expense Rejected',
        'description': 'Your expense has been rejected and requires attention.',
        'color': '#dc3545',
    },
    'expense_level_approved': {
        'title': 'Expense Level Approved',
        'description': 'Your expense has been approved at one level and is proceeding to the next approval level.',
        'color': '#17a2b8',
    },
    'expense_fully_approved': {
        'title': 'Expense Fully Approved',
        'description': 'Your expense has been fully approved and is ready for reimbursement.',
        'color': '#28a745',
    },
    'expense_auto_approved': {
        'title': 'Expense Auto-Approved',
        'description': 'Your expense has been automatically approved based on company policies.',
        'color': '#28a745',
    },
    'approval_reminder': {
        'title': 'Approval Reminder',
        'description': 'You have pending expense approvals that require your attention.',
        'color': '#fd7e14',
    },
    'approval_escalation': {
        'title': 'Approval Escalation',
        'description': 'An expense approval is overdue and requires immediate attention.',
        'color': '#dc3545',
    },

    # Invoice Approval events
    'invoice_submitted_for_approval': {
        'title': 'Invoice Submitted for Approval',
        'description': 'An invoice has been submitted and requires your approval.',
        'color': '#ffc107',
    },
    'invoice_fully_approved': {
        'title': 'Invoice Fully Approved',
        'description': 'Your invoice has been fully approved.',
        'color': '#28a745',
    },
    'invoice_rejected': {
        'title': 'Invoice Rejected',
        'description': 'Your invoice has been rejected and requires attention.',
        'color': '#dc3545',
    },
}


def get_event_info(event_type: str, resource_type: str) -> Dict[str, str]:
    """Return display metadata for a notification event.

    Falls back to a generic title/description/color when ``event_type`` is not
    in :data:`EVENT_INFO`, derived from the resource type and event slug.
    """
    return EVENT_INFO.get(event_type, {
        'title': f'{resource_type.title()} {event_type.replace("_", " ").title()}',
        'description': f'A {resource_type} operation has occurred.',
        'color': '#6c757d',
    })
