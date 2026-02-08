"""Add personality_type as JSONB with MBTI values

Revision ID: 010_add_personality_type_jsonb
Revises: 009_add_love_map_tables
Create Date: 2025-01-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_add_personality_type_jsonb'
down_revision = '009_add_love_map_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if personality_type column exists
    op.execute("""
        DO $$ 
        BEGIN
            -- If column doesn't exist, create it as JSONB
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='users' 
                AND column_name='personality_type'
            ) THEN
                ALTER TABLE users ADD COLUMN personality_type JSONB;
            -- If column exists as VARCHAR, convert it to JSONB
            ELSIF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='users' 
                AND column_name='personality_type'
                AND data_type='character varying'
            ) THEN
                -- Convert existing VARCHAR values to JSONB format
                UPDATE users 
                SET personality_type = CASE
                    WHEN personality_type IS NULL THEN NULL
                    WHEN personality_type = 'Prefer not to say' THEN '{"type": "Prefer not to say"}'::jsonb
                    WHEN LENGTH(personality_type) = 4 THEN 
                        jsonb_build_object('type', personality_type)
                    ELSE '{"type": "Prefer not to say"}'::jsonb
                END
                WHERE personality_type IS NOT NULL;
                
                -- Change column type to JSONB
                ALTER TABLE users ALTER COLUMN personality_type TYPE jsonb USING personality_type::jsonb;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Convert JSONB back to VARCHAR (losing the values, keeping only type)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='users' 
                AND column_name='personality_type'
                AND data_type='jsonb'
            ) THEN
                -- Extract type from JSONB and convert to VARCHAR
                UPDATE users 
                SET personality_type = CASE
                    WHEN personality_type IS NULL THEN NULL
                    WHEN personality_type->>'type' IS NOT NULL THEN personality_type->>'type'
                    ELSE NULL
                END
                WHERE personality_type IS NOT NULL;
                
                -- Change column type back to VARCHAR
                ALTER TABLE users ALTER COLUMN personality_type TYPE VARCHAR USING personality_type::VARCHAR;
            END IF;
        END $$;
    """)
