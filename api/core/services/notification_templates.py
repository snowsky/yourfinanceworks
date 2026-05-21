"""Jinja templates for notification emails.

Extracted out of :mod:`notification_service` so the service file is not
dominated by ~700 lines of inline HTML and text. The Template objects are
constructed once at import time and reused across requests.
"""

from jinja2 import Template

# Generic operation notification (user, client, invoice, payment, settings events).
OPERATION_HTML_TEMPLATE = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .event-badge {
                    display: inline-block;
                    background-color: {{ event_color }};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .details {
                    background-color: #f8f9fa;
                    border-left: 4px solid {{ event_color }};
                    padding: 15px;
                    margin: 20px 0;
                }
                .details-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .detail-item {
                    margin: 5px 0;
                    font-size: 14px;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
                .timestamp {
                    color: #999;
                    font-size: 12px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">{{ event_title }}</h1>
                    <span class="event-badge">{{ event_type.replace('_', ' ').title() }}</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p>{{ event_description }}</p>
                </div>
                
                <div class="details">
                    <div class="details-title">Details:</div>
                    <div class="detail-item"><strong>{{ resource_type.title() }}:</strong> {{ resource_name }}</div>
                    {% for key, value in details.items() %}
                    <div class="detail-item"><strong>{{ key.replace('_', ' ').title() }}:</strong> {{ value }}</div>
                    {% endfor %}
                    <div class="timestamp">{{ timestamp }}</div>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification from {{ company_name }}.</p>
                    <p>You can manage your notification preferences in your account settings.</p>
                </div>
            </div>
        </body>
        </html>
        """)

OPERATION_TEXT_TEMPLATE = Template("""
        {{ company_name }} - {{ event_title }}
        
        Hello {{ recipient_name }},
        
        {{ event_description }}
        
        Details:
        {{ resource_type.title() }}: {{ resource_name }}
        {% for key, value in details.items() %}
        {{ key.replace('_', ' ').title() }}: {{ value }}
        {% endfor %}
        
        Timestamp: {{ timestamp }}
        
        This is an automated notification from {{ company_name }}.
        You can manage your notification preferences in your account settings.
        """)

# Approval reminder for pending expense approvals.
APPROVAL_REMINDER_HTML_TEMPLATE = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .reminder-badge {
                    display: inline-block;
                    background-color: #fd7e14;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .summary-box {
                    background-color: #fff3cd;
                    border: 1px solid #ffeaa7;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }
                .summary-item {
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                    font-size: 16px;
                }
                .summary-label {
                    font-weight: bold;
                    color: #333;
                }
                .summary-value {
                    color: #666;
                }
                .pending-list {
                    background-color: #f8f9fa;
                    border-left: 4px solid #fd7e14;
                    padding: 15px;
                    margin: 20px 0;
                }
                .pending-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .action-button {
                    display: inline-block;
                    background-color: #fd7e14;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
                .timestamp {
                    color: #999;
                    font-size: 12px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">Pending Approvals Reminder</h1>
                    <span class="reminder-badge">Action Required</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p>You have <strong>{{ pending_count }}</strong> expense approval{{ 's' if pending_count != 1 else '' }} waiting for your review.</p>
                </div>
                
                <div class="summary-box">
                    <div class="summary-item">
                        <span class="summary-label">Total Pending:</span>
                        <span class="summary-value">{{ details.total_pending }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Total Amount:</span>
                        <span class="summary-value">{{ details.total_amount }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Oldest Submission:</span>
                        <span class="summary-value">{{ details.oldest_submission }}</span>
                    </div>
                </div>
                
                <div class="pending-list">
                    <div class="pending-title">Pending Expenses:</div>
                    <div>{{ details.pending_list }}</div>
                    {% if details.additional_count %}
                    <div style="margin-top: 10px; font-style: italic;">
                        ... and {{ details.additional_count }} more
                    </div>
                    {% endif %}
                </div>
                
                <div style="text-align: center;">
                    <a href="#" class="action-button">Review Pending Approvals</a>
                </div>
                
                <div class="footer">
                    <p>This is an automated reminder from {{ company_name }}.</p>
                    <p>You can manage your notification preferences in your account settings.</p>
                    <div class="timestamp">{{ timestamp }}</div>
                </div>
            </div>
        </body>
        </html>
        """)

APPROVAL_REMINDER_TEXT_TEMPLATE = Template("""
        {{ company_name }} - Pending Approvals Reminder
        
        Hello {{ recipient_name }},
        
        You have {{ pending_count }} expense approval{{ 's' if pending_count != 1 else '' }} waiting for your review.
        
        Summary:
        - Total Pending: {{ details.total_pending }}
        - Total Amount: {{ details.total_amount }}
        - Oldest Submission: {{ details.oldest_submission }}
        
        Pending Expenses:
        {{ details.pending_list }}
        {% if details.additional_count %}
        ... and {{ details.additional_count }} more
        {% endif %}
        
        Please log in to review and approve these expenses.
        
        Timestamp: {{ timestamp }}
        
        This is an automated reminder from {{ company_name }}.
        You can manage your notification preferences in your account settings.
        """)

# Approval escalation for overdue expense approvals.
APPROVAL_ESCALATION_HTML_TEMPLATE = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #dc3545;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .urgent-badge {
                    display: inline-block;
                    background-color: #dc3545;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0% { opacity: 1; }
                    50% { opacity: 0.7; }
                    100% { opacity: 1; }
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .alert-box {
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 20px 0;
                }
                .summary-item {
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                    font-size: 16px;
                }
                .summary-label {
                    font-weight: bold;
                    color: #333;
                }
                .summary-value {
                    color: #666;
                }
                .overdue-list {
                    background-color: #f8f9fa;
                    border-left: 4px solid #dc3545;
                    padding: 15px;
                    margin: 20px 0;
                }
                .overdue-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .action-button {
                    display: inline-block;
                    background-color: #dc3545;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
                .timestamp {
                    color: #999;
                    font-size: 12px;
                    margin-top: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">Overdue Approvals Escalation</h1>
                    <span class="urgent-badge">URGENT</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p><strong>{{ details.approver_name }}</strong> has <strong>{{ overdue_count }}</strong> overdue expense approval{{ 's' if overdue_count != 1 else '' }} that require immediate attention.</p>
                    <p>These approvals have exceeded the expected response time and may be impacting employee reimbursements.</p>
                </div>
                
                <div class="alert-box">
                    <div class="summary-item">
                        <span class="summary-label">Approver:</span>
                        <span class="summary-value">{{ details.approver_name }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Total Overdue:</span>
                        <span class="summary-value">{{ details.total_overdue }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Total Amount:</span>
                        <span class="summary-value">{{ details.total_amount }}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Oldest Submission:</span>
                        <span class="summary-value">{{ details.oldest_submission }}</span>
                    </div>
                </div>
                
                <div class="overdue-list">
                    <div class="overdue-title">Overdue Expenses:</div>
                    <div>{{ details.overdue_list }}</div>
                    {% if details.additional_count %}
                    <div style="margin-top: 10px; font-style: italic;">
                        ... and {{ details.additional_count }} more
                    </div>
                    {% endif %}
                </div>
                
                <div style="text-align: center;">
                    <a href="#" class="action-button">Take Action</a>
                </div>
                
                <div class="footer">
                    <p>This is an automated escalation from {{ company_name }}.</p>
                    <p>Please follow up with the approver or take appropriate action to resolve these overdue approvals.</p>
                    <div class="timestamp">{{ timestamp }}</div>
                </div>
            </div>
        </body>
        </html>
        """)

APPROVAL_ESCALATION_TEXT_TEMPLATE = Template("""
        {{ company_name }} - URGENT: Overdue Approvals Escalation
        
        Hello {{ recipient_name }},
        
        {{ details.approver_name }} has {{ overdue_count }} overdue expense approval{{ 's' if overdue_count != 1 else '' }} that require immediate attention.
        
        These approvals have exceeded the expected response time and may be impacting employee reimbursements.
        
        Details:
        - Approver: {{ details.approver_name }}
        - Total Overdue: {{ details.total_overdue }}
        - Total Amount: {{ details.total_amount }}
        - Oldest Submission: {{ details.oldest_submission }}
        
        Overdue Expenses:
        {{ details.overdue_list }}
        {% if details.additional_count %}
        ... and {{ details.additional_count }} more
        {% endif %}
        
        Please follow up with the approver or take appropriate action to resolve these overdue approvals.
        
        Timestamp: {{ timestamp }}
        
        This is an automated escalation from {{ company_name }}.
        """)

# Daily approval digest summarizing recent activity.
APPROVAL_DIGEST_HTML_TEMPLATE = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ subject }}</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #f0f0f0;
                }
                .logo {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                }
                .title {
                    color: #333;
                    font-size: 20px;
                    margin-bottom: 10px;
                }
                .digest-badge {
                    display: inline-block;
                    background-color: #17a2b8;
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 12px;
                    font-weight: bold;
                    text-transform: uppercase;
                }
                .content {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 30px;
                }
                .digest-section {
                    margin: 20px 0;
                    padding: 15px;
                    border-left: 4px solid #17a2b8;
                    background-color: #f8f9fa;
                }
                .section-title {
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 16px;
                }
                .digest-item {
                    margin: 8px 0;
                    padding: 8px;
                    background-color: white;
                    border-radius: 4px;
                    border-left: 3px solid #28a745;
                }
                .digest-item.rejected {
                    border-left-color: #dc3545;
                }
                .digest-item.pending {
                    border-left-color: #ffc107;
                }
                .item-title {
                    font-weight: bold;
                    color: #333;
                }
                .item-details {
                    font-size: 14px;
                    color: #666;
                    margin-top: 4px;
                }
                .summary-stats {
                    display: flex;
                    justify-content: space-around;
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #e9ecef;
                    border-radius: 8px;
                }
                .stat-item {
                    text-align: center;
                }
                .stat-number {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333;
                }
                .stat-label {
                    font-size: 12px;
                    color: #666;
                    text-transform: uppercase;
                }
                .action-button {
                    display: inline-block;
                    background-color: #17a2b8;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                    text-align: center;
                }
                .footer {
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 14px;
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">{{ company_name }}</div>
                    <h1 class="title">Daily Approval Digest</h1>
                    <span class="digest-badge">{{ digest_date }}</span>
                </div>
                
                <div class="content">
                    <p>Hello {{ recipient_name }},</p>
                    <p>Here's your daily summary of approval activities:</p>
                </div>
                
                <div class="summary-stats">
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.total_events or 0 }}</div>
                        <div class="stat-label">Total Events</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.pending_count or 0 }}</div>
                        <div class="stat-label">Pending</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.approved_count or 0 }}</div>
                        <div class="stat-label">Approved</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{{ digest_data.rejected_count or 0 }}</div>
                        <div class="stat-label">Rejected</div>
                    </div>
                </div>
                
                {% if digest_data.pending_approvals %}
                <div class="digest-section">
                    <div class="section-title">Pending Approvals</div>
                    {% for approval in digest_data.pending_approvals %}
                    <div class="digest-item pending">
                        <div class="item-title">Expense #{{ approval.expense_id }} - {{ approval.category }}</div>
                        <div class="item-details">
                            Amount: ${{ approval.amount }} | Submitted: {{ approval.submitted_at }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if digest_data.approved_expenses %}
                <div class="digest-section">
                    <div class="section-title">Recently Approved</div>
                    {% for expense in digest_data.approved_expenses %}
                    <div class="digest-item">
                        <div class="item-title">Expense #{{ expense.expense_id }} - {{ expense.category }}</div>
                        <div class="item-details">
                            Amount: ${{ expense.amount }} | Approved: {{ expense.approved_at }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if digest_data.rejected_expenses %}
                <div class="digest-section">
                    <div class="section-title">Recently Rejected</div>
                    {% for expense in digest_data.rejected_expenses %}
                    <div class="digest-item rejected">
                        <div class="item-title">Expense #{{ expense.expense_id }} - {{ expense.category }}</div>
                        <div class="item-details">
                            Amount: ${{ expense.amount }} | Rejected: {{ expense.rejected_at }}
                            <br>Reason: {{ expense.rejection_reason }}
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <div style="text-align: center;">
                    <a href="#" class="action-button">View All Approvals</a>
                </div>
                
                <div class="footer">
                    <p>This is your daily approval digest from {{ company_name }}.</p>
                    <p>You can change your notification preferences in your account settings.</p>
                </div>
            </div>
        </body>
        </html>
        """)

APPROVAL_DIGEST_TEXT_TEMPLATE = Template("""
        {{ company_name }} - Daily Approval Digest
        {{ digest_date }}
        
        Hello {{ recipient_name }},
        
        Here's your daily summary of approval activities:
        
        Summary:
        - Total Events: {{ digest_data.total_events or 0 }}
        - Pending: {{ digest_data.pending_count or 0 }}
        - Approved: {{ digest_data.approved_count or 0 }}
        - Rejected: {{ digest_data.rejected_count or 0 }}
        
        {% if digest_data.pending_approvals %}
        Pending Approvals:
        {% for approval in digest_data.pending_approvals %}
        - Expense #{{ approval.expense_id }} ({{ approval.category }}) - ${{ approval.amount }}
          Submitted: {{ approval.submitted_at }}
        {% endfor %}
        {% endif %}
        
        {% if digest_data.approved_expenses %}
        Recently Approved:
        {% for expense in digest_data.approved_expenses %}
        - Expense #{{ expense.expense_id }} ({{ expense.category }}) - ${{ expense.amount }}
          Approved: {{ expense.approved_at }}
        {% endfor %}
        {% endif %}
        
        {% if digest_data.rejected_expenses %}
        Recently Rejected:
        {% for expense in digest_data.rejected_expenses %}
        - Expense #{{ expense.expense_id }} ({{ expense.category }}) - ${{ expense.amount }}
          Rejected: {{ expense.rejected_at }}
          Reason: {{ expense.rejection_reason }}
        {% endfor %}
        {% endif %}
        
        This is your daily approval digest from {{ company_name }}.
        You can change your notification preferences in your account settings.
        """)
