"""Add voice_embedding_json to voice_profiles

Revision ID: 012_add_voice_embedding_json
Revises: 011_add_voice_sample_base64
Create Date: 2026-01-27 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '012_add_voice_embedding_json'
down_revision = '011_add_voice_sample_base64'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='voice_profiles' AND column_name='voice_embedding_json'
            ) THEN
                ALTER TABLE voice_profiles ADD COLUMN voice_embedding_json TEXT;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_column('voice_profiles', 'voice_embedding_json')
"""Add voice_embedding_json to voice_profiles

Revision ID: 012_add_voice_embedding_json
Revises: 011_add_voice_sample_base64
Create Date: 2026-01-27 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "012_add_voice_embedding_json"
down_revision = "011_add_voice_sample_base64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='voice_profiles' AND column_name='voice_embedding_json'
            ) THEN
                ALTER TABLE voice_profiles ADD COLUMN voice_embedding_json TEXT;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_column("voice_profiles", "voice_embedding_json")
