"""add_invoice_attachment_columns

Revision ID: 38f8e053a17e
Revises: 467164d8d5af
Create Date: 2025-08-06 03:09:26.870331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38f8e053a17e'
down_revision: Union[str, Sequence[str], None] = '467164d8d5af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'invoices' not in tables:
        return
    columns = [c['name'] for c in inspector.get_columns('invoices')]
    if 'attachment_path' not in columns:
        op.add_column('invoices', sa.Column('attachment_path', sa.String(), nullable=True))
    if 'attachment_filename' not in columns:
        op.add_column('invoices', sa.Column('attachment_filename', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'invoices' not in tables:
        return
    columns = [c['name'] for c in inspector.get_columns('invoices')]
    if 'attachment_filename' in columns:
        op.drop_column('invoices', 'attachment_filename')
    if 'attachment_path' in columns:
        op.drop_column('invoices', 'attachment_path')
