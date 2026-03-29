"""Add workflow tables

Revision ID: 010_add_workflow_tables
Revises: 009_add_notes_to_transactions
Create Date: 2026-03-29 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_add_workflow_tables'
down_revision: Union[str, Sequence[str], None] = '009_add_notes_to_transactions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workflow_definitions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_type', sa.String(), nullable=False),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('actions', sa.JSON(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index(op.f('ix_workflow_definitions_id'), 'workflow_definitions', ['id'], unique=False)
    op.create_index(op.f('ix_workflow_definitions_key'), 'workflow_definitions', ['key'], unique=False)
    op.create_index(op.f('ix_workflow_definitions_trigger_type'), 'workflow_definitions', ['trigger_type'], unique=False)

    op.create_table(
        'workflow_execution_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('event_key', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='success'),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflow_definitions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_id', 'event_key', name='uq_workflow_execution_event'),
    )
    op.create_index(op.f('ix_workflow_execution_logs_id'), 'workflow_execution_logs', ['id'], unique=False)
    op.create_index(op.f('ix_workflow_execution_logs_workflow_id'), 'workflow_execution_logs', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_workflow_execution_logs_entity_type'), 'workflow_execution_logs', ['entity_type'], unique=False)
    op.create_index(op.f('ix_workflow_execution_logs_entity_id'), 'workflow_execution_logs', ['entity_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_workflow_execution_logs_entity_id'), table_name='workflow_execution_logs')
    op.drop_index(op.f('ix_workflow_execution_logs_entity_type'), table_name='workflow_execution_logs')
    op.drop_index(op.f('ix_workflow_execution_logs_workflow_id'), table_name='workflow_execution_logs')
    op.drop_index(op.f('ix_workflow_execution_logs_id'), table_name='workflow_execution_logs')
    op.drop_table('workflow_execution_logs')

    op.drop_index(op.f('ix_workflow_definitions_trigger_type'), table_name='workflow_definitions')
    op.drop_index(op.f('ix_workflow_definitions_key'), table_name='workflow_definitions')
    op.drop_index(op.f('ix_workflow_definitions_id'), table_name='workflow_definitions')
    op.drop_table('workflow_definitions')
