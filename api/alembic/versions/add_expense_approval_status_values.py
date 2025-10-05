"""Add expense approval status values

Revision ID: add_expense_approval_status_values
Revises: add_expense_approval_workflow_tables
Create Date: 2025-01-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_expense_approval_status_values'
down_revision = 'add_expense_approval_workflow_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add check constraint for expense status values to support approval workflow"""
    
    # Define all valid status values
    valid_statuses = [
        'draft',
        'recorded', 
        'reimbursed',
        'pending_approval',
        'approved',
        'rejected',
        'resubmitted'
    ]
    
    # Create check constraint for expense status
    status_constraint = "status IN ({})".format(', '.join([f"'{status}'" for status in valid_statuses]))
    
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('expenses') as batch_op:
        batch_op.create_check_constraint(
            'ck_expense_status_valid',
            status_constraint
        )


def downgrade():
    """Remove the expense status check constraint"""
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('expenses') as batch_op:
        batch_op.drop_constraint('ck_expense_status_valid', type_='check')