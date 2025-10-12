"""add_is_read_column_to_reminder_notifications

Revision ID: 3db559573430
Revises: a856713febd7
Create Date: 2025-10-12 16:25:14.290412

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3db559573430'
down_revision: Union[str, Sequence[str], None] = 'a856713febd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_read column to reminder_notifications table
    op.add_column('reminder_notifications', sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'))

    # Update existing records to have is_read = false
    op.execute("UPDATE reminder_notifications SET is_read = false WHERE is_read IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_read column from reminder_notifications table
    op.drop_column('reminder_notifications', 'is_read')
