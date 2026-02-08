"""Add profile_picture_url to users

Revision ID: 005_add_profile_picture
Revises: 004_add_emoji_to_pokes
Create Date: 2026-01-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005_add_profile_picture'
down_revision = '004_add_emoji_to_pokes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add profile_picture_url column to users table (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='profile_picture_url') THEN
                ALTER TABLE users ADD COLUMN profile_picture_url VARCHAR;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove profile_picture_url column from users table
    op.drop_column('users', 'profile_picture_url')
