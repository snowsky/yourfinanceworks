"""Add time tracking tables

Revision ID: 006_time_tracking
Revises: 005_add_tenant_id_to_investment_tables
Create Date: 2026-03-02 21:47:49.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_time_tracking'
down_revision = '005_add_tenant_id'
branch_labels = None
depends_on = None



def upgrade():
    """Add project and time tracking tables"""

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('billing_method', sa.String(), nullable=False, server_default='hourly'),
        sa.Column('fixed_amount', sa.Float(), nullable=True),
        sa.Column('budget_hours', sa.Float(), nullable=True),
        sa.Column('budget_amount', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_projects_id', 'projects', ['id'])
    op.create_index('ix_projects_client_id', 'projects', ['client_id'])
    op.create_index('ix_projects_status', 'projects', ['status'])

    # Create project_tasks table
    op.create_table(
        'project_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('estimated_hours', sa.Float(), nullable=True),
        sa.Column('hourly_rate', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_project_tasks_id', 'project_tasks', ['id'])
    op.create_index('ix_project_tasks_project_id', 'project_tasks', ['project_id'])

    # Create time_entries table
    op.create_table(
        'time_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('hourly_rate', sa.Float(), nullable=False),
        sa.Column('billable', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='in_progress'),
        sa.Column('invoiced', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('invoice_number', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['project_tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_time_entries_id', 'time_entries', ['id'])
    op.create_index('ix_time_entries_project_id', 'time_entries', ['project_id'])
    op.create_index('ix_time_entries_user_id', 'time_entries', ['user_id'])
    op.create_index('ix_time_entries_client_id', 'time_entries', ['client_id'])
    op.create_index('ix_time_entries_status', 'time_entries', ['status'])
    op.create_index('ix_time_entries_invoiced', 'time_entries', ['invoiced'])
    op.create_index('ix_time_entries_started_at', 'time_entries', ['started_at'])


def downgrade():
    """Remove time tracking tables"""
    op.drop_table('time_entries')
    op.drop_table('project_tasks')
    op.drop_table('projects')
