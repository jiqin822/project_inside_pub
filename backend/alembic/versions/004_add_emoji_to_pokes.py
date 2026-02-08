"""Add emoji column to poke_events

Revision ID: 004_add_emoji_to_pokes
Revises: 003_realtime_sessions
Create Date: 2026-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_emoji_to_pokes'
down_revision = '003_realtime_sessions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add emoji column to poke_events table (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='poke_events' AND column_name='emoji') THEN
                ALTER TABLE poke_events ADD COLUMN emoji VARCHAR;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove emoji column from poke_events table
    op.drop_column('poke_events', 'emoji')
