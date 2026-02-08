"""Add market tables

Revision ID: 006_add_market_tables
Revises: 005_add_profile_picture
Create Date: 2026-01-27 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ENUM


# revision identifiers, used by Alembic.
revision = '006_add_market_tables'
down_revision = '005_add_profile_picture'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM types
    transaction_category_enum = ENUM('SPEND', 'EARN', name='transaction_category', create_type=True)
    transaction_status_enum = ENUM(
        'PURCHASED', 'REDEEMED', 'ACCEPTED', 'PENDING_APPROVAL', 'APPROVED', 'CANCELED',
        name='transaction_status',
        create_type=True
    )
    
    # Create economy_settings table
    op.create_table(
        'economy_settings',
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('currency_name', sa.String(), nullable=False),
        sa.Column('currency_symbol', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # Create wallets table
    op.create_table(
        'wallets',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('issuer_id', sa.String(), nullable=False),
        sa.Column('holder_id', sa.String(), nullable=False),
        sa.Column('balance', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['issuer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['holder_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('issuer_id', 'holder_id', name='uq_wallet_issuer_holder'),
        sa.CheckConstraint('balance >= 0', name='ck_wallet_balance_non_negative')
    )
    op.create_index('ix_wallets_issuer_id', 'wallets', ['issuer_id'], unique=False)
    op.create_index('ix_wallets_holder_id', 'wallets', ['holder_id'], unique=False)
    
    # Create market_items table
    op.create_table(
        'market_items',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('issuer_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('cost', sa.Integer(), nullable=False),
        sa.Column('icon', sa.String(), nullable=True),
        sa.Column('category', transaction_category_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['issuer_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('cost > 0', name='ck_market_item_cost_positive')
    )
    op.create_index('ix_market_items_issuer_id', 'market_items', ['issuer_id'], unique=False)
    op.create_index('ix_market_items_is_active', 'market_items', ['is_active'], unique=False)
    
    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('wallet_id', sa.String(), nullable=False),
        sa.Column('market_item_id', sa.String(), nullable=True),
        sa.Column('category', transaction_category_enum, nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('status', transaction_status_enum, nullable=False),
        sa.Column('tx_metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['wallet_id'], ['wallets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['market_item_id'], ['market_items.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount > 0', name='ck_transaction_amount_positive')
    )
    op.create_index('ix_transactions_wallet_id', 'transactions', ['wallet_id'], unique=False)
    op.create_index('ix_transactions_market_item_id', 'transactions', ['market_item_id'], unique=False)
    op.create_index('ix_transactions_status', 'transactions', ['status'], unique=False)
    op.create_index('ix_transactions_created_at', 'transactions', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_transactions_created_at', table_name='transactions')
    op.drop_index('ix_transactions_status', table_name='transactions')
    op.drop_index('ix_transactions_market_item_id', table_name='transactions')
    op.drop_index('ix_transactions_wallet_id', table_name='transactions')
    op.drop_table('transactions')
    
    op.drop_index('ix_market_items_is_active', table_name='market_items')
    op.drop_index('ix_market_items_issuer_id', table_name='market_items')
    op.drop_table('market_items')
    
    op.drop_index('ix_wallets_holder_id', table_name='wallets')
    op.drop_index('ix_wallets_issuer_id', table_name='wallets')
    op.drop_table('wallets')
    
    op.drop_table('economy_settings')
    
    # Drop ENUM types
    op.execute("DROP TYPE IF EXISTS transaction_status")
    op.execute("DROP TYPE IF EXISTS transaction_category")
