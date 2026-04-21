"""Add investment management tables

Revision ID: 003_investment_tables
Revises: 002_add_social_features_tables
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_investment_tables'
down_revision = '002_add_timeliness_bonus'  # Latest revision
branch_labels = None
depends_on = None

def upgrade():
    """Create investment tables"""

    # Create enum types for investment management
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'portfoliotype') THEN
            CREATE TYPE portfoliotype AS ENUM ('TAXABLE', 'RETIREMENT', 'BUSINESS');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'securitytype') THEN
            CREATE TYPE securitytype AS ENUM ('STOCK', 'BOND', 'ETF', 'MUTUAL_FUND', 'CASH');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assetclass') THEN
            CREATE TYPE assetclass AS ENUM ('STOCKS', 'BONDS', 'CASH', 'REAL_ESTATE', 'COMMODITIES');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transactiontype') THEN
            CREATE TYPE transactiontype AS ENUM ('BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE', 'TRANSFER', 'CONTRIBUTION');
        END IF;
    END $$;
    """)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dividendtype') THEN
            CREATE TYPE dividendtype AS ENUM ('ORDINARY');
        END IF;
    END $$;
    """)

    # Create investment_portfolios table
    op.create_table(
        'investment_portfolios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),  # For explicit tenant isolation
        sa.Column('name', sa.String(), nullable=False),  # Will be encrypted by EncryptedColumn
        sa.Column('portfolio_type', postgresql.ENUM('TAXABLE', 'RETIREMENT', 'BUSINESS', name='portfoliotype'), nullable=False),
        sa.Column('is_archived', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for investment_portfolios
    op.create_index('ix_investment_portfolios_id', 'investment_portfolios', ['id'])
    op.create_index('ix_investment_portfolios_tenant_id', 'investment_portfolios', ['tenant_id'])
    op.create_index('ix_investment_portfolios_name', 'investment_portfolios', ['name'])
    op.create_index('ix_investment_portfolios_portfolio_type', 'investment_portfolios', ['portfolio_type'])
    op.create_index('ix_investment_portfolios_created_at', 'investment_portfolios', ['created_at'])

    # Create investment_holdings table
    op.create_table(
        'investment_holdings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('security_symbol', sa.String(20), nullable=False),
        sa.Column('security_name', sa.String(), nullable=True),  # Will be encrypted by EncryptedColumn
        sa.Column('security_type', postgresql.ENUM('STOCK', 'BOND', 'ETF', 'MUTUAL_FUND', 'CASH', name='securitytype'), nullable=False),
        sa.Column('asset_class', postgresql.ENUM('STOCKS', 'BONDS', 'CASH', 'REAL_ESTATE', 'COMMODITIES', name='assetclass'), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('cost_basis', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=False),
        sa.Column('current_price', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('price_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_closed', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['investment_portfolios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('quantity > 0', name='ck_investment_holdings_positive_quantity'),
        sa.CheckConstraint('cost_basis > 0', name='ck_investment_holdings_positive_cost_basis'),
        sa.CheckConstraint('current_price IS NULL OR current_price > 0', name='ck_investment_holdings_positive_price')
    )

    # Create indexes for investment_holdings
    op.create_index('ix_investment_holdings_id', 'investment_holdings', ['id'])
    op.create_index('ix_investment_holdings_portfolio_id', 'investment_holdings', ['portfolio_id'])
    op.create_index('ix_investment_holdings_security_symbol', 'investment_holdings', ['security_symbol'])
    op.create_index('ix_investment_holdings_security_type', 'investment_holdings', ['security_type'])
    op.create_index('ix_investment_holdings_asset_class', 'investment_holdings', ['asset_class'])
    op.create_index('ix_investment_holdings_is_closed', 'investment_holdings', ['is_closed'])

    # Create investment_transactions table
    op.create_table(
        'investment_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('holding_id', sa.Integer(), nullable=True),  # Nullable for cash transactions
        sa.Column('transaction_type', postgresql.ENUM('BUY', 'SELL', 'DIVIDEND', 'INTEREST', 'FEE', 'TRANSFER', 'CONTRIBUTION', name='transactiontype'), nullable=False),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=18, scale=8), nullable=True),  # Nullable for dividends, fees, etc.
        sa.Column('price_per_share', sa.Numeric(precision=18, scale=2), nullable=True),  # Nullable for dividends, fees, etc.
        sa.Column('total_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('fees', sa.Numeric(precision=18, scale=2), nullable=False, default=0),
        sa.Column('realized_gain', sa.Numeric(precision=18, scale=2), nullable=True),  # For SELL transactions
        sa.Column('dividend_type', postgresql.ENUM('ORDINARY', name='dividendtype'), nullable=True),  # For DIVIDEND transactions
        sa.Column('payment_date', sa.Date(), nullable=True),  # For DIVIDEND transactions
        sa.Column('ex_dividend_date', sa.Date(), nullable=True),  # For DIVIDEND transactions
        sa.Column('notes', sa.String(), nullable=True),  # Will be encrypted by EncryptedColumn
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['investment_portfolios.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['holding_id'], ['investment_holdings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('total_amount != 0', name='ck_investment_transactions_nonzero_amount'),
        sa.CheckConstraint('fees >= 0', name='ck_investment_transactions_non_negative_fees'),
        sa.CheckConstraint('quantity IS NULL OR quantity > 0', name='ck_investment_transactions_positive_quantity'),
        sa.CheckConstraint('price_per_share IS NULL OR price_per_share > 0', name='ck_investment_transactions_positive_price')
    )

    # Create indexes for investment_transactions
    op.create_index('ix_investment_transactions_id', 'investment_transactions', ['id'])
    op.create_index('ix_investment_transactions_portfolio_id', 'investment_transactions', ['portfolio_id'])
    op.create_index('ix_investment_transactions_holding_id', 'investment_transactions', ['holding_id'])
    op.create_index('ix_investment_transactions_transaction_type', 'investment_transactions', ['transaction_type'])
    op.create_index('ix_investment_transactions_transaction_date', 'investment_transactions', ['transaction_date'])

    # Create composite indexes for common queries
    op.create_index('ix_investment_transactions_portfolio_date', 'investment_transactions', ['portfolio_id', 'transaction_date'])
    op.create_index('ix_investment_transactions_holding_date', 'investment_transactions', ['holding_id', 'transaction_date'])


def downgrade():
    """Drop investment tables"""

    # Drop indexes first
    op.drop_index('ix_investment_transactions_holding_date', 'investment_transactions')
    op.drop_index('ix_investment_transactions_portfolio_date', 'investment_transactions')
    op.drop_index('ix_investment_transactions_transaction_date', 'investment_transactions')
    op.drop_index('ix_investment_transactions_transaction_type', 'investment_transactions')
    op.drop_index('ix_investment_transactions_holding_id', 'investment_transactions')
    op.drop_index('ix_investment_transactions_portfolio_id', 'investment_transactions')
    op.drop_index('ix_investment_transactions_id', 'investment_transactions')

    op.drop_index('ix_investment_holdings_is_closed', 'investment_holdings')
    op.drop_index('ix_investment_holdings_asset_class', 'investment_holdings')
    op.drop_index('ix_investment_holdings_security_type', 'investment_holdings')
    op.drop_index('ix_investment_holdings_security_symbol', 'investment_holdings')
    op.drop_index('ix_investment_holdings_portfolio_id', 'investment_holdings')
    op.drop_index('ix_investment_holdings_id', 'investment_holdings')

    op.drop_index('ix_investment_portfolios_created_at', 'investment_portfolios')
    op.drop_index('ix_investment_portfolios_portfolio_type', 'investment_portfolios')
    op.drop_index('ix_investment_portfolios_name', 'investment_portfolios')
    op.drop_index('ix_investment_portfolios_tenant_id', 'investment_portfolios')
    op.drop_index('ix_investment_portfolios_id', 'investment_portfolios')

    # Drop tables
    op.drop_table('investment_transactions')
    op.drop_table('investment_holdings')
    op.drop_table('investment_portfolios')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS dividendtype')
    op.execute('DROP TYPE IF EXISTS transactiontype')
    op.execute('DROP TYPE IF EXISTS assetclass')
    op.execute('DROP TYPE IF EXISTS securitytype')
    op.execute('DROP TYPE IF EXISTS portfoliotype')
