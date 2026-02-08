"""Realtime sessions schema migration

Revision ID: 003_realtime_sessions
Revises: 002_onboarding
Create Date: 2024-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_realtime_sessions'
down_revision = '002_onboarding'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sessionstatus') THEN
                CREATE TYPE sessionstatus AS ENUM ('ACTIVE', 'ENDED', 'FINALIZED');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reportstatus') THEN
                CREATE TYPE reportstatus AS ENUM ('PENDING', 'READY');
            END IF;
        END $$;
    """)
    
    # Update sessions table
    op.execute("""
        DO $$ 
        BEGIN
            -- Add new columns if they don't exist
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='started_at') THEN
                ALTER TABLE sessions ADD COLUMN started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='ended_at') THEN
                ALTER TABLE sessions ADD COLUMN ended_at TIMESTAMP;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sessions' AND column_name='created_by_user_id') THEN
                ALTER TABLE sessions ADD COLUMN created_by_user_id VARCHAR;
            END IF;
            
            -- Update existing rows to set defaults
            UPDATE sessions SET started_at = created_at WHERE started_at IS NULL;
            UPDATE sessions SET status = 'ACTIVE' WHERE status IS NULL OR status = 'active' OR status = 'draft';
            UPDATE sessions SET status = 'ENDED' WHERE status = 'ended' OR status = 'finalized';
        END $$;
    """)
    
    # Convert status column to enum (if not already)
    op.execute("""
        DO $$ 
        BEGIN
            -- Drop default if present so PostgreSQL can cast column to enum (default cannot be cast automatically)
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'sessions'
                AND column_name = 'status' AND column_default IS NOT NULL
            ) THEN
                ALTER TABLE sessions ALTER COLUMN status DROP DEFAULT;
            END IF;
            
            -- Check if column is already enum type
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='sessions' 
                AND column_name='status' 
                AND udt_name != 'sessionstatus'
            ) THEN
                -- Convert to enum
                ALTER TABLE sessions ALTER COLUMN status TYPE sessionstatus USING status::sessionstatus;
            END IF;
            
            -- Set NOT NULL and default
            ALTER TABLE sessions ALTER COLUMN status SET DEFAULT 'ACTIVE'::sessionstatus;
            ALTER TABLE sessions ALTER COLUMN status SET NOT NULL;
            ALTER TABLE sessions ALTER COLUMN started_at SET NOT NULL;
            ALTER TABLE sessions ALTER COLUMN created_by_user_id SET NOT NULL;
        END $$;
    """)
    
    # Update session_reports table
    op.execute("""
        DO $$ 
        BEGIN
            -- Add status column if it doesn't exist
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='session_reports' AND column_name='status') THEN
                ALTER TABLE session_reports ADD COLUMN status reportstatus DEFAULT 'PENDING'::reportstatus;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='session_reports' AND column_name='updated_at') THEN
                ALTER TABLE session_reports ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            END IF;
            
            -- Make summary nullable
            ALTER TABLE session_reports ALTER COLUMN summary DROP NOT NULL;
            
            -- Set default for moments and action_items if they're null
            UPDATE session_reports SET moments = '[]'::jsonb WHERE moments IS NULL;
            UPDATE session_reports SET action_items = '[]'::jsonb WHERE action_items IS NULL;
        END $$;
    """)
    
    # Create session_feature_frames table
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='session_feature_frames') THEN
                CREATE TABLE session_feature_frames (
                    id VARCHAR NOT NULL PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    timestamp_ms BIGINT NOT NULL,
                    speaking_rate DOUBLE PRECISION NOT NULL,
                    overlap_ratio DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_session_feature_frames_session 
                        FOREIGN KEY (session_id) REFERENCES sessions(id),
                    CONSTRAINT fk_session_feature_frames_user 
                        FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE INDEX idx_session_feature_frames_session_id ON session_feature_frames(session_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop session_feature_frames table
    op.execute("DROP TABLE IF EXISTS session_feature_frames;")
    
    # Revert session_reports changes
    op.execute("""
        ALTER TABLE session_reports DROP COLUMN IF EXISTS status;
        ALTER TABLE session_reports DROP COLUMN IF EXISTS updated_at;
        ALTER TABLE session_reports ALTER COLUMN summary SET NOT NULL;
    """)
    
    # Revert sessions table changes
    op.execute("""
        ALTER TABLE sessions DROP COLUMN IF EXISTS started_at;
        ALTER TABLE sessions DROP COLUMN IF EXISTS ended_at;
        ALTER TABLE sessions DROP COLUMN IF EXISTS created_by_user_id;
        ALTER TABLE sessions ALTER COLUMN status TYPE VARCHAR USING status::text;
    """)
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS reportstatus;")
    op.execute("DROP TYPE IF EXISTS sessionstatus;")
