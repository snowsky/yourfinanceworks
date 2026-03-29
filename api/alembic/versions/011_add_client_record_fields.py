"""Add client record fields

Revision ID: 011_add_client_record_fields
Revises: 010_add_workflow_tables
Create Date: 2026-03-29 13:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_add_client_record_fields'
down_revision: Union[str, Sequence[str], None] = '010_add_workflow_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('owner_user_id', sa.Integer(), nullable=True))
    op.add_column('clients', sa.Column('stage', sa.String(), nullable=False, server_default='active_client'))
    op.add_column('clients', sa.Column('relationship_status', sa.String(), nullable=False, server_default='healthy'))
    op.add_column('clients', sa.Column('source', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('last_contact_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('clients', sa.Column('next_follow_up_at', sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        'fk_clients_owner_user_id',
        'clients',
        'users',
        ['owner_user_id'],
        ['id'],
    )
    op.create_index('ix_clients_owner_user_id', 'clients', ['owner_user_id'])


def downgrade() -> None:
    op.drop_index('ix_clients_owner_user_id', table_name='clients')
    op.drop_constraint('fk_clients_owner_user_id', 'clients', type_='foreignkey')
    op.drop_column('clients', 'next_follow_up_at')
    op.drop_column('clients', 'last_contact_at')
    op.drop_column('clients', 'source')
    op.drop_column('clients', 'relationship_status')
    op.drop_column('clients', 'stage')
    op.drop_column('clients', 'owner_user_id')
