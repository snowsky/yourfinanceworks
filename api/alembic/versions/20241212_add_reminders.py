"""Add reminders system

Revision ID: 20241212_add_reminders
Revises: (previous revision)
Create Date: 2024-12-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20241212_add_reminders'
down_revision = None  # Update this with the actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Create reminders table
    op.create_table('reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('next_due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('recurrence_pattern', sa.Enum('none', 'daily', 'weekly', 'monthly', 'yearly', name='recurrencepattern'), nullable=False),
        sa.Column('recurrence_interval', sa.Integer(), nullable=False),
        sa.Column('recurrence_end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('pending', 'completed', 'snoozed', 'cancelled', name='reminderstatus'), nullable=False),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', 'urgent', name='reminderpriority'), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to_id', sa.Integer(), nullable=False),
        sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('snooze_count', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by_id', sa.Integer(), nullable=True),
        sa.Column('completion_notes', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['completed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['deleted_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reminders_id'), 'reminders', ['id'], unique=False)
    op.create_index(op.f('ix_reminders_title'), 'reminders', ['title'], unique=False)

    # Create reminder_notifications table
    op.create_table('reminder_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reminder_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(), nullable=False),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_sent', sa.Boolean(), nullable=False),
        sa.Column('send_attempts', sa.Integer(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['reminder_id'], ['reminders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reminder_id', 'user_id', 'notification_type', 'scheduled_for', name='unique_reminder_notification')
    )
    op.create_index(op.f('ix_reminder_notifications_id'), 'reminder_notifications', ['id'], unique=False)

    # Add reminder notification fields to email_notification_settings
    op.add_column('email_notification_settings', sa.Column('reminder_due', sa.Boolean(), nullable=True))
    op.add_column('email_notification_settings', sa.Column('reminder_overdue', sa.Boolean(), nullable=True))
    op.add_column('email_notification_settings', sa.Column('reminder_upcoming', sa.Boolean(), nullable=True))
    op.add_column('email_notification_settings', sa.Column('reminder_assigned', sa.Boolean(), nullable=True))
    op.add_column('email_notification_settings', sa.Column('reminder_completed', sa.Boolean(), nullable=True))
    op.add_column('email_notification_settings', sa.Column('reminder_advance_days', sa.Integer(), nullable=True))
    op.add_column('email_notification_settings', sa.Column('reminder_notification_frequency', sa.String(), nullable=True))

    # Set default values for reminder notification settings
    op.execute("UPDATE email_notification_settings SET reminder_due = true WHERE reminder_due IS NULL")
    op.execute("UPDATE email_notification_settings SET reminder_overdue = true WHERE reminder_overdue IS NULL")
    op.execute("UPDATE email_notification_settings SET reminder_upcoming = true WHERE reminder_upcoming IS NULL")
    op.execute("UPDATE email_notification_settings SET reminder_assigned = true WHERE reminder_assigned IS NULL")
    op.execute("UPDATE email_notification_settings SET reminder_completed = false WHERE reminder_completed IS NULL")
    op.execute("UPDATE email_notification_settings SET reminder_advance_days = 1 WHERE reminder_advance_days IS NULL")
    op.execute("UPDATE email_notification_settings SET reminder_notification_frequency = 'immediate' WHERE reminder_notification_frequency IS NULL")

    # Make columns non-nullable after setting defaults
    op.alter_column('email_notification_settings', 'reminder_due', nullable=False)
    op.alter_column('email_notification_settings', 'reminder_overdue', nullable=False)
    op.alter_column('email_notification_settings', 'reminder_upcoming', nullable=False)
    op.alter_column('email_notification_settings', 'reminder_assigned', nullable=False)
    op.alter_column('email_notification_settings', 'reminder_completed', nullable=False)
    op.alter_column('email_notification_settings', 'reminder_advance_days', nullable=False)
    op.alter_column('email_notification_settings', 'reminder_notification_frequency', nullable=False)


def downgrade():
    # Remove reminder notification columns from email_notification_settings
    op.drop_column('email_notification_settings', 'reminder_notification_frequency')
    op.drop_column('email_notification_settings', 'reminder_advance_days')
    op.drop_column('email_notification_settings', 'reminder_completed')
    op.drop_column('email_notification_settings', 'reminder_assigned')
    op.drop_column('email_notification_settings', 'reminder_upcoming')
    op.drop_column('email_notification_settings', 'reminder_overdue')
    op.drop_column('email_notification_settings', 'reminder_due')

    # Drop reminder_notifications table
    op.drop_index(op.f('ix_reminder_notifications_id'), table_name='reminder_notifications')
    op.drop_table('reminder_notifications')

    # Drop reminders table
    op.drop_index(op.f('ix_reminders_title'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_id'), table_name='reminders')
    op.drop_table('reminders')

    # Drop custom enum types
    op.execute('DROP TYPE IF EXISTS reminderpriority')
    op.execute('DROP TYPE IF EXISTS reminderstatus')
    op.execute('DROP TYPE IF EXISTS recurrencepattern')
