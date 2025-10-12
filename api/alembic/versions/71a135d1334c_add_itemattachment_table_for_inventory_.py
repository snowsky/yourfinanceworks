"""Add ItemAttachment table for inventory attachments

Revision ID: 71a135d1334c
Revises: 3b6c4742cb45
Create Date: 2025-09-17 22:29:55.923953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71a135d1334c'
down_revision: Union[str, Sequence[str], None] = '3b6c4742cb45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create item_attachments table
    op.create_table(
        'item_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('stored_filename', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('content_type', sa.String(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False),
        sa.Column('attachment_type', sa.String(), nullable=False),
        sa.Column('document_type', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alt_text', sa.String(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, default=False),
        sa.Column('display_order', sa.Integer(), nullable=False, default=0),
        sa.Column('image_width', sa.Integer(), nullable=True),
        sa.Column('image_height', sa.Integer(), nullable=True),
        sa.Column('has_thumbnail', sa.Boolean(), nullable=False, default=False),
        sa.Column('thumbnail_path', sa.String(), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('upload_ip', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for performance
    op.create_index('idx_item_attachments_id', 'item_attachments', ['id'], unique=False)
    op.create_index('idx_item_attachments_item_id', 'item_attachments', ['item_id'], unique=False)
    op.create_index('idx_item_attachments_type', 'item_attachments', ['attachment_type'], unique=False)
    op.create_index('idx_item_attachments_primary', 'item_attachments', ['item_id', 'is_primary'], unique=False)
    op.create_index('idx_item_attachments_order', 'item_attachments', ['item_id', 'display_order'], unique=False)
    op.create_index('idx_item_attachments_file_hash', 'item_attachments', ['file_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_item_attachments_file_hash', table_name='item_attachments')
    op.drop_index('idx_item_attachments_order', table_name='item_attachments')
    op.drop_index('idx_item_attachments_primary', table_name='item_attachments')
    op.drop_index('idx_item_attachments_type', table_name='item_attachments')
    op.drop_index('idx_item_attachments_item_id', table_name='item_attachments')
    op.drop_index('idx_item_attachments_id', table_name='item_attachments')

    # Drop table
    op.drop_table('item_attachments')
