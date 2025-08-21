"""fix bank transaction foreign key constraints for deletion

Revision ID: fix_bank_txn_fk_constraints_001
Revises: add_bank_txn_invoice_link_001  
Create Date: 2025-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fix_bank_txn_fk_constraints_001'
down_revision: Union[str, Sequence[str], None] = ('2b1b_must_reset_password_tenant', 'add_bank_statement_labels_array_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update foreign key constraints to SET NULL on delete"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    
    if 'bank_statement_transactions' not in tables:
        return
        
    # Get existing foreign keys
    fks = inspector.get_foreign_keys('bank_statement_transactions')
    
    try:
        # Drop and recreate expense_id foreign key with SET NULL
        expense_fk_name = None
        for fk in fks:
            if fk['constrained_columns'] == ['expense_id']:
                expense_fk_name = fk['name']
                break
        
        if expense_fk_name:
            op.drop_constraint(expense_fk_name, 'bank_statement_transactions', type_='foreignkey')
        
        op.create_foreign_key(
            'fk_bank_statement_transactions_expense_id_v2',
            'bank_statement_transactions', 
            'expenses',
            ['expense_id'], 
            ['id'],
            ondelete='SET NULL'
        )
        
        # Drop and recreate invoice_id foreign key with SET NULL  
        invoice_fk_name = None
        for fk in fks:
            if fk['constrained_columns'] == ['invoice_id']:
                invoice_fk_name = fk['name']
                break
                
        if invoice_fk_name:
            op.drop_constraint(invoice_fk_name, 'bank_statement_transactions', type_='foreignkey')
            
        op.create_foreign_key(
            'fk_bank_statement_transactions_invoice_id_v2',
            'bank_statement_transactions',
            'invoices', 
            ['invoice_id'],
            ['id'],
            ondelete='SET NULL'
        )
        
    except Exception as e:
        # If FK operations fail, continue - some databases might not support this
        print(f"Warning: Could not update foreign key constraints: {e}")


def downgrade() -> None:
    """Revert foreign key constraints to original state"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    
    if 'bank_statement_transactions' not in tables:
        return
        
    try:
        # Drop the new constraints
        op.drop_constraint('fk_bank_statement_transactions_expense_id_v2', 'bank_statement_transactions', type_='foreignkey')
        op.drop_constraint('fk_bank_statement_transactions_invoice_id_v2', 'bank_statement_transactions', type_='foreignkey')
        
        # Recreate original constraints (without ondelete)
        op.create_foreign_key(
            'fk_bank_statement_transactions_expense_id',
            'bank_statement_transactions',
            'expenses', 
            ['expense_id'],
            ['id']
        )
        
        op.create_foreign_key(
            'fk_bank_statement_transactions_invoice_id', 
            'bank_statement_transactions',
            'invoices',
            ['invoice_id'], 
            ['id']
        )
        
    except Exception as e:
        print(f"Warning: Could not revert foreign key constraints: {e}")
