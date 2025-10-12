"""merge multiple heads

Revision ID: a856713febd7
Revises: 20241212_add_reminders, 71a135d1334c, add_approval_notification_preferences, add_approval_notification_settings, update_approval_workflow_indexes
Create Date: 2025-10-12 15:55:13.625624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a856713febd7'
down_revision: Union[str, Sequence[str], None] = ('20241212_add_reminders', '71a135d1334c', 'add_approval_notification_preferences', 'add_approval_notification_settings', 'update_approval_workflow_indexes')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
