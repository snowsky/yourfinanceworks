"""Add reporting tables

Revision ID: add_reporting_tables
Revises: 951a7ee5381c
Create Date: 2025-01-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_reporting_tables'
down_revision = '951a7ee5381c'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Create report_templates table
    if 'report_templates' not in existing_tables:
        op.create_table(
            'report_templates',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('report_type', sa.String(), nullable=False),
            sa.Column('filters', sa.JSON(), nullable=True),
            sa.Column('columns', sa.JSON(), nullable=True),
            sa.Column('formatting', sa.JSON(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('is_shared', sa.Boolean(), nullable=False, default=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_report_templates_id'), 'report_templates', ['id'], unique=False)
        op.create_index(op.f('ix_report_templates_user_id'), 'report_templates', ['user_id'], unique=False)
        op.create_index(op.f('ix_report_templates_report_type'), 'report_templates', ['report_type'], unique=False)
        op.create_index(op.f('ix_report_templates_is_shared'), 'report_templates', ['is_shared'], unique=False)

    # Create scheduled_reports table
    if 'scheduled_reports' not in existing_tables:
        op.create_table(
            'scheduled_reports',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('template_id', sa.Integer(), nullable=False),
            sa.Column('schedule_type', sa.String(), nullable=False),
            sa.Column('schedule_config', sa.JSON(), nullable=False),
            sa.Column('recipients', sa.JSON(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
            sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
            sa.Column('next_run', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_scheduled_reports_id'), 'scheduled_reports', ['id'], unique=False)
        op.create_index(op.f('ix_scheduled_reports_template_id'), 'scheduled_reports', ['template_id'], unique=False)
        op.create_index(op.f('ix_scheduled_reports_is_active'), 'scheduled_reports', ['is_active'], unique=False)
        op.create_index(op.f('ix_scheduled_reports_next_run'), 'scheduled_reports', ['next_run'], unique=False)

    # Create report_history table
    if 'report_history' not in existing_tables:
        op.create_table(
            'report_history',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('template_id', sa.Integer(), nullable=True),
            sa.Column('report_type', sa.String(), nullable=False),
            sa.Column('parameters', sa.JSON(), nullable=False),
            sa.Column('file_path', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=False, default='pending'),
            sa.Column('generated_by', sa.Integer(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], ),
            sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_report_history_id'), 'report_history', ['id'], unique=False)
        op.create_index(op.f('ix_report_history_template_id'), 'report_history', ['template_id'], unique=False)
        op.create_index(op.f('ix_report_history_generated_by'), 'report_history', ['generated_by'], unique=False)
        op.create_index(op.f('ix_report_history_report_type'), 'report_history', ['report_type'], unique=False)
        op.create_index(op.f('ix_report_history_status'), 'report_history', ['status'], unique=False)
        op.create_index(op.f('ix_report_history_generated_at'), 'report_history', ['generated_at'], unique=False)
        op.create_index(op.f('ix_report_history_expires_at'), 'report_history', ['expires_at'], unique=False)

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Drop report_history table
    if 'report_history' in existing_tables:
        op.drop_index(op.f('ix_report_history_expires_at'), table_name='report_history')
        op.drop_index(op.f('ix_report_history_generated_at'), table_name='report_history')
        op.drop_index(op.f('ix_report_history_status'), table_name='report_history')
        op.drop_index(op.f('ix_report_history_report_type'), table_name='report_history')
        op.drop_index(op.f('ix_report_history_generated_by'), table_name='report_history')
        op.drop_index(op.f('ix_report_history_template_id'), table_name='report_history')
        op.drop_index(op.f('ix_report_history_id'), table_name='report_history')
        op.drop_table('report_history')

    # Drop scheduled_reports table
    if 'scheduled_reports' in existing_tables:
        op.drop_index(op.f('ix_scheduled_reports_next_run'), table_name='scheduled_reports')
        op.drop_index(op.f('ix_scheduled_reports_is_active'), table_name='scheduled_reports')
        op.drop_index(op.f('ix_scheduled_reports_template_id'), table_name='scheduled_reports')
        op.drop_index(op.f('ix_scheduled_reports_id'), table_name='scheduled_reports')
        op.drop_table('scheduled_reports')

    # Drop report_templates table
    if 'report_templates' in existing_tables:
        op.drop_index(op.f('ix_report_templates_is_shared'), table_name='report_templates')
        op.drop_index(op.f('ix_report_templates_report_type'), table_name='report_templates')
        op.drop_index(op.f('ix_report_templates_user_id'), table_name='report_templates')
        op.drop_index(op.f('ix_report_templates_id'), table_name='report_templates')
        op.drop_table('report_templates')