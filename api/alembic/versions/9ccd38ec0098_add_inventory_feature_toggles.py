"""add_inventory_feature_toggles

Revision ID: 9ccd38ec0098
Revises: e2f2296cfcbc
Create Date: 2025-09-15 11:28:22.341194

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ccd38ec0098'
down_revision: Union[str, Sequence[str], None] = 'e2f2296cfcbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add business_type column to users table
    op.add_column('users', sa.Column('business_type', sa.String(), nullable=True, default='service'))

    # Add description, category, and is_public columns to settings table
    op.add_column('settings', sa.Column('description', sa.String(), nullable=True))
    op.add_column('settings', sa.Column('category', sa.String(), nullable=True, default='general'))
    op.add_column('settings', sa.Column('is_public', sa.Boolean(), nullable=True, default=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns in reverse order
    op.drop_column('settings', 'is_public')
    op.drop_column('settings', 'category')
    op.drop_column('settings', 'description')
    op.drop_column('users', 'business_type')
