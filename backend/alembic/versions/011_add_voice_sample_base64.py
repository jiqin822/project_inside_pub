"""Add voice_sample_base64 to voice_profiles

Revision ID: 011_add_voice_sample_base64
Revises: ace00b639bf8
Create Date: 2026-01-27 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '011_add_voice_sample_base64'
down_revision = 'ace00b639bf8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='voice_profiles' AND column_name='voice_sample_base64') THEN
                ALTER TABLE voice_profiles ADD COLUMN voice_sample_base64 TEXT;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column('voice_profiles', 'voice_sample_base64')
