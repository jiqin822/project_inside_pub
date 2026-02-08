"""Add market item relationships junction table

Revision ID: 007_market_item_rel
Revises: 006_add_market_tables
Create Date: 2026-01-27 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic (≤32 chars for default alembic_version.version_num).
revision = '007_market_item_rel'
down_revision = '006_add_market_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create junction table for market items and relationships (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='market_item_relationships') THEN
                CREATE TABLE market_item_relationships (
                    market_item_id VARCHAR NOT NULL,
                    relationship_id VARCHAR NOT NULL,
                    PRIMARY KEY (market_item_id, relationship_id),
                    FOREIGN KEY(market_item_id) REFERENCES market_items (id) ON DELETE CASCADE,
                    FOREIGN KEY(relationship_id) REFERENCES relationships (id) ON DELETE CASCADE
                );
                
                CREATE INDEX ix_market_item_relationships_market_item_id ON market_item_relationships (market_item_id);
                CREATE INDEX ix_market_item_relationships_relationship_id ON market_item_relationships (relationship_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_index('ix_market_item_relationships_relationship_id', table_name='market_item_relationships')
    op.drop_index('ix_market_item_relationships_market_item_id', table_name='market_item_relationships')
    op.drop_table('market_item_relationships')
