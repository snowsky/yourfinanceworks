"""merge all heads

Revision ID: 88e9df861f9b
Revises: 002_social_features, 007_project_expenses, add_audit_fields, create_prompt_templates
Create Date: 2026-03-11 17:51:53.501821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88e9df861f9b'
down_revision: Union[str, Sequence[str], None] = ('002_social_features', '007_project_expenses', 'add_audit_fields', 'create_prompt_templates')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
