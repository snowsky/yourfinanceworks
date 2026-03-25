"""Create prompt templates table

Revision ID: create_prompt_templates
Revises: previous_migration
Create Date: 2025-12-14 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'create_prompt_templates'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create prompt_templates and prompt_usage_logs tables."""
    
    # Create prompt_templates table
    try:
        op.create_table(
            'prompt_templates',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('template_content', sa.Text(), nullable=False),
            sa.Column('template_variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('output_format', sa.String(length=20), nullable=True, server_default='json'),
            sa.Column('default_values', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
            sa.Column('provider_overrides', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('updated_by', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['created_by'], ['master_users.id'], ),
            sa.ForeignKeyConstraint(['updated_by'], ['master_users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_prompt_templates_category'), 'prompt_templates', ['category'], unique=False)
        op.create_index(op.f('ix_prompt_templates_name'), 'prompt_templates', ['name'], unique=False)
    except Exception as e:
        print(f"Skipping prompt_templates creation: {e}")
    
    # Create prompt_usage_logs table
    try:
        op.create_table(
            'prompt_usage_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('template_id', sa.Integer(), nullable=False),
            sa.Column('tenant_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('provider_name', sa.String(length=50), nullable=False),
            sa.Column('model_name', sa.String(length=100), nullable=False),
            sa.Column('processing_time_ms', sa.Integer(), nullable=True),
            sa.Column('token_count', sa.Integer(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('input_preview', sa.Text(), nullable=True),
            sa.Column('output_preview', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.ForeignKeyConstraint(['template_id'], ['prompt_templates.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['master_users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_prompt_usage_logs_template_id'), 'prompt_usage_logs', ['template_id'], unique=False)
        op.create_index(op.f('ix_prompt_usage_logs_tenant_id'), 'prompt_usage_logs', ['tenant_id'], unique=False)
    except Exception as e:
        print(f"Skipping prompt_usage_logs creation: {e}")


def downgrade():
    """Drop prompt_templates and prompt_usage_logs tables."""
    op.drop_index(op.f('ix_prompt_usage_logs_tenant_id'), table_name='prompt_usage_logs')
    op.drop_index(op.f('ix_prompt_usage_logs_template_id'), table_name='prompt_usage_logs')
    op.drop_table('prompt_usage_logs')
    op.drop_index(op.f('ix_prompt_templates_name'), table_name='prompt_templates')
    op.drop_index(op.f('ix_prompt_templates_category'), table_name='prompt_templates')
    op.drop_table('prompt_templates')
