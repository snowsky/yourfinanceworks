"""Add approval notification preferences

Revision ID: add_approval_notification_preferences
Revises: add_reporting_tables
Create Date: 2025-01-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_approval_notification_preferences'
down_revision = 'add_reporting_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to email_notification_settings table
    op.add_column('email_notification_settings', 
                  sa.Column('approval_notification_frequency', sa.String(), nullable=False, server_default='immediate'))
    op.add_column('email_notification_settings', 
                  sa.Column('approval_reminder_frequency', sa.String(), nullable=False, server_default='daily'))
    op.add_column('email_notification_settings', 
                  sa.Column('approval_notification_channels', sa.JSON(), nullable=False, server_default='["email"]'))


def downgrade():
    # Remove the added columns
    op.drop_column('email_notification_settings', 'approval_notification_channels')
    op.drop_column('email_notification_settings', 'approval_reminder_frequency')
    op.drop_column('email_notification_settings', 'approval_notification_frequency')