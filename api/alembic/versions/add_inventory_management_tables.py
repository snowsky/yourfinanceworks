"""Add inventory management tables

Revision ID: add_inventory_management_001
Revises: add_disable_ai_recognition_001
Create Date: 2025-09-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_inventory_management_001'
down_revision = 'add_disable_ai_recognition_001'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Create inventory_categories table
    if 'inventory_categories' not in existing_tables:
        op.create_table(
            'inventory_categories',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('color', sa.String(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_inventory_categories_id'), 'inventory_categories', ['id'], unique=False)
        op.create_index(op.f('ix_inventory_categories_name'), 'inventory_categories', ['name'], unique=True)

    # Create inventory_items table
    if 'inventory_items' not in existing_tables:
        op.create_table(
            'inventory_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('sku', sa.String(), nullable=True),
            sa.Column('category_id', sa.Integer(), nullable=True),
            sa.Column('unit_price', sa.Float(), nullable=False),
            sa.Column('cost_price', sa.Float(), nullable=True),
            sa.Column('currency', sa.String(), nullable=False, default='USD'),
            sa.Column('track_stock', sa.Boolean(), nullable=False, default=False),
            sa.Column('current_stock', sa.Float(), nullable=False, default=0.0),
            sa.Column('minimum_stock', sa.Float(), nullable=False, default=0.0),
            sa.Column('unit_of_measure', sa.String(), nullable=False, default='each'),
            sa.Column('item_type', sa.String(), nullable=False, default='product'),
            sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['category_id'], ['inventory_categories.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_inventory_items_id'), 'inventory_items', ['id'], unique=False)
        op.create_index(op.f('ix_inventory_items_name'), 'inventory_items', ['name'], unique=False)
        op.create_index(op.f('ix_inventory_items_sku'), 'inventory_items', ['sku'], unique=True)
        op.create_index(op.f('ix_inventory_items_category_id'), 'inventory_items', ['category_id'], unique=False)
        op.create_index(op.f('ix_inventory_items_item_type'), 'inventory_items', ['item_type'], unique=False)
        op.create_index(op.f('ix_inventory_items_is_active'), 'inventory_items', ['is_active'], unique=False)

    # Create stock_movements table
    if 'stock_movements' not in existing_tables:
        op.create_table(
            'stock_movements',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('item_id', sa.Integer(), nullable=False),
            sa.Column('movement_type', sa.String(), nullable=False),
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('unit_cost', sa.Float(), nullable=True),
            sa.Column('reference_type', sa.String(), nullable=True),
            sa.Column('reference_id', sa.Integer(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('movement_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['item_id'], ['inventory_items.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_stock_movements_id'), 'stock_movements', ['id'], unique=False)
        op.create_index(op.f('ix_stock_movements_item_id'), 'stock_movements', ['item_id'], unique=False)
        op.create_index(op.f('ix_stock_movements_movement_type'), 'stock_movements', ['movement_type'], unique=False)
        op.create_index(op.f('ix_stock_movements_reference_type'), 'stock_movements', ['reference_type'], unique=False)
        op.create_index(op.f('ix_stock_movements_user_id'), 'stock_movements', ['user_id'], unique=False)
        op.create_index(op.f('ix_stock_movements_movement_date'), 'stock_movements', ['movement_date'], unique=False)

    # Add inventory fields to invoice_items table
    existing_cols_invoice_items = {c['name'] for c in inspector.get_columns('invoice_items')}
    if 'inventory_item_id' not in existing_cols_invoice_items:
        op.add_column('invoice_items', sa.Column('inventory_item_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_invoice_items_inventory_item_id', 'invoice_items', 'inventory_items', ['inventory_item_id'], ['id'])
        op.create_index(op.f('ix_invoice_items_inventory_item_id'), 'invoice_items', ['inventory_item_id'], unique=False)

    if 'unit_of_measure' not in existing_cols_invoice_items:
        op.add_column('invoice_items', sa.Column('unit_of_measure', sa.String(), nullable=True))

    # Add inventory fields to expenses table
    existing_cols_expenses = {c['name'] for c in inspector.get_columns('expenses')}
    if 'is_inventory_purchase' not in existing_cols_expenses:
        op.add_column('expenses', sa.Column('is_inventory_purchase', sa.Boolean(), nullable=False, default=False))

    if 'inventory_items' not in existing_cols_expenses:
        op.add_column('expenses', sa.Column('inventory_items', sa.JSON(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # Remove inventory fields from expenses table
    existing_cols_expenses = {c['name'] for c in inspector.get_columns('expenses')}
    if 'inventory_items' in existing_cols_expenses:
        op.drop_column('expenses', 'inventory_items')
    if 'is_inventory_purchase' in existing_cols_expenses:
        op.drop_column('expenses', 'is_inventory_purchase')

    # Remove inventory fields from invoice_items table
    existing_cols_invoice_items = {c['name'] for c in inspector.get_columns('invoice_items')}
    if 'unit_of_measure' in existing_cols_invoice_items:
        op.drop_column('invoice_items', 'unit_of_measure')
    if 'inventory_item_id' in existing_cols_invoice_items:
        op.drop_index(op.f('ix_invoice_items_inventory_item_id'), table_name='invoice_items')
        op.drop_constraint('fk_invoice_items_inventory_item_id', 'invoice_items', type_='foreignkey')
        op.drop_column('invoice_items', 'inventory_item_id')

    # Drop stock_movements table
    if 'stock_movements' in existing_tables:
        op.drop_index(op.f('ix_stock_movements_movement_date'), table_name='stock_movements')
        op.drop_index(op.f('ix_stock_movements_user_id'), table_name='stock_movements')
        op.drop_index(op.f('ix_stock_movements_reference_type'), table_name='stock_movements')
        op.drop_index(op.f('ix_stock_movements_movement_type'), table_name='stock_movements')
        op.drop_index(op.f('ix_stock_movements_item_id'), table_name='stock_movements')
        op.drop_index(op.f('ix_stock_movements_id'), table_name='stock_movements')
        op.drop_table('stock_movements')

    # Drop inventory_items table
    if 'inventory_items' in existing_tables:
        op.drop_index(op.f('ix_inventory_items_is_active'), table_name='inventory_items')
        op.drop_index(op.f('ix_inventory_items_item_type'), table_name='inventory_items')
        op.drop_index(op.f('ix_inventory_items_category_id'), table_name='inventory_items')
        op.drop_index(op.f('ix_inventory_items_sku'), table_name='inventory_items')
        op.drop_index(op.f('ix_inventory_items_name'), table_name='inventory_items')
        op.drop_index(op.f('ix_inventory_items_id'), table_name='inventory_items')
        op.drop_table('inventory_items')

    # Drop inventory_categories table
    if 'inventory_categories' in existing_tables:
        op.drop_index(op.f('ix_inventory_categories_name'), table_name='inventory_categories')
        op.drop_index(op.f('ix_inventory_categories_id'), table_name='inventory_categories')
        op.drop_table('inventory_categories')
