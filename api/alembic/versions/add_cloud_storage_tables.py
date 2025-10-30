"""Add cloud storage configuration and operation logging tables

This migration adds support for cloud storage by creating:
1. CloudStorageConfiguration table for storing provider configurations
2. StorageOperationLog table for audit logging of storage operations

Revision ID: add_cloud_storage_tables
Revises: 
Create Date: 2025-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import logging

# revision identifiers, used by Alembic.
revision = 'add_cloud_storage_tables'
down_revision = 'c9d955fdb70c'  # Connecting to the main migration chain
depends_on = None

logger = logging.getLogger(__name__)


def upgrade():
    """
    Create cloud storage configuration and operation logging tables.
    """
    
    logger.info("Starting cloud storage tables migration...")
    
    # Create CloudStorageConfiguration table
    logger.info("Creating cloud_storage_configurations table...")
    op.create_table(
        'cloud_storage_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('encrypted_configuration', sa.Text(), nullable=False),
        sa.Column('configuration_version', sa.Integer(), nullable=False),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('test_status', sa.String(length=20), nullable=True),
        sa.Column('test_error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for CloudStorageConfiguration
    op.create_index(op.f('ix_cloud_storage_configurations_id'), 'cloud_storage_configurations', ['id'], unique=False)
    op.create_index(op.f('ix_cloud_storage_configurations_tenant_id'), 'cloud_storage_configurations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_cloud_storage_configurations_provider'), 'cloud_storage_configurations', ['provider'], unique=False)
    
    # Create unique constraint for tenant_id + provider combination
    op.create_index('ix_cloud_storage_config_tenant_provider', 'cloud_storage_configurations', ['tenant_id', 'provider'], unique=True)
    
    # Create StorageOperationLog table
    logger.info("Creating storage_operation_logs table...")
    op.create_table(
        'storage_operation_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('operation_type', sa.String(length=20), nullable=False),
        sa.Column('file_key', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(length=100), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for StorageOperationLog
    op.create_index(op.f('ix_storage_operation_logs_id'), 'storage_operation_logs', ['id'], unique=False)
    op.create_index(op.f('ix_storage_operation_logs_tenant_id'), 'storage_operation_logs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_storage_operation_logs_operation_type'), 'storage_operation_logs', ['operation_type'], unique=False)
    op.create_index(op.f('ix_storage_operation_logs_file_key'), 'storage_operation_logs', ['file_key'], unique=False)
    op.create_index(op.f('ix_storage_operation_logs_provider'), 'storage_operation_logs', ['provider'], unique=False)
    op.create_index(op.f('ix_storage_operation_logs_success'), 'storage_operation_logs', ['success'], unique=False)
    op.create_index(op.f('ix_storage_operation_logs_created_at'), 'storage_operation_logs', ['created_at'], unique=False)
    
    # Create composite indexes for common queries
    op.create_index('ix_storage_logs_tenant_created', 'storage_operation_logs', ['tenant_id', 'created_at'], unique=False)
    op.create_index('ix_storage_logs_operation_created', 'storage_operation_logs', ['operation_type', 'created_at'], unique=False)
    op.create_index('ix_storage_logs_provider_success', 'storage_operation_logs', ['provider', 'success'], unique=False)
    
    logger.info("Cloud storage tables created successfully.")


def downgrade():
    """
    Drop cloud storage configuration and operation logging tables.
    """
    
    logger.info("Starting cloud storage tables rollback...")
    
    # Drop StorageOperationLog table and its indexes
    logger.info("Dropping storage_operation_logs table...")
    op.drop_index('ix_storage_logs_provider_success', table_name='storage_operation_logs')
    op.drop_index('ix_storage_logs_operation_created', table_name='storage_operation_logs')
    op.drop_index('ix_storage_logs_tenant_created', table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_created_at'), table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_success'), table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_provider'), table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_file_key'), table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_operation_type'), table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_tenant_id'), table_name='storage_operation_logs')
    op.drop_index(op.f('ix_storage_operation_logs_id'), table_name='storage_operation_logs')
    op.drop_table('storage_operation_logs')
    
    # Drop CloudStorageConfiguration table and its indexes
    logger.info("Dropping cloud_storage_configurations table...")
    op.drop_index('ix_cloud_storage_config_tenant_provider', table_name='cloud_storage_configurations')
    op.drop_index(op.f('ix_cloud_storage_configurations_provider'), table_name='cloud_storage_configurations')
    op.drop_index(op.f('ix_cloud_storage_configurations_tenant_id'), table_name='cloud_storage_configurations')
    op.drop_index(op.f('ix_cloud_storage_configurations_id'), table_name='cloud_storage_configurations')
    op.drop_table('cloud_storage_configurations')
    
    logger.info("Cloud storage tables rollback complete.")
