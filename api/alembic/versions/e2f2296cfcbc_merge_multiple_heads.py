"""merge_multiple_heads

Revision ID: e2f2296cfcbc
Revises: 7cc88c42e7f4, add_inventory_management_001, add_reporting_tables
Create Date: 2025-09-15 11:28:17.749980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f2296cfcbc'
down_revision: Union[str, Sequence[str], None] = ('7cc88c42e7f4', 'add_inventory_management_001', 'add_reporting_tables')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
