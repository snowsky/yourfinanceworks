"""Add approval notification settings

Revision ID: add_approval_notification_settings
Revises: add_expense_approval_workflow_tables
Create Date: 2024-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_approval_notification_settings'
down_revision = 'add_expense_approval_workflow_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add approval notification settings columns to email_notification_settings table."""
    
    # Add approval notification columns
    op.add_column('email_notification_settings', 
                  sa.Column('expense_submitted_for_approval', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('expense_approved', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('expense_rejected', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('expense_level_approved', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('expense_fully_approved', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('expense_auto_approved', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('approval_reminder', sa.Boolean(), nullable=False, default=True))
    op.add_column('email_notification_settings', 
                  sa.Column('approval_escalation', sa.Boolean(), nullable=False, default=True))


def downgrade():
    """Remove approval notification settings columns."""
    
    # Remove approval notification columns
    op.drop_column('email_notification_settings', 'approval_escalation')
    op.drop_column('email_notification_settings', 'approval_reminder')
    op.drop_column('email_notification_settings', 'expense_auto_approved')
    op.drop_column('email_notification_settings', 'expense_fully_approved')
    op.drop_column('email_notification_settings', 'expense_level_approved')
    op.drop_column('email_notification_settings', 'expense_rejected')
    op.drop_column('email_notification_settings', 'expense_approved')
    op.drop_column('email_notification_settings', 'expense_submitted_for_approval')