"""Onboarding schema migration

Revision ID: 002_onboarding
Revises: 001_initial
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_onboarding'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table (only if they don't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='pronouns') THEN
                ALTER TABLE users ADD COLUMN pronouns VARCHAR;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='communication_style') THEN
                ALTER TABLE users ADD COLUMN communication_style DOUBLE PRECISION;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='goals') THEN
                ALTER TABLE users ADD COLUMN goals JSONB;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='privacy_tier') THEN
                ALTER TABLE users ADD COLUMN privacy_tier VARCHAR;
            END IF;
        END $$;
    """)
    
    # Create onboarding_progress table (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='onboarding_progress') THEN
                CREATE TABLE onboarding_progress (
                    user_id VARCHAR NOT NULL,
                    profile_completed BOOLEAN NOT NULL DEFAULT false,
                    voiceprint_completed BOOLEAN NOT NULL DEFAULT false,
                    relationships_completed BOOLEAN NOT NULL DEFAULT false,
                    consent_completed BOOLEAN NOT NULL DEFAULT false,
                    device_setup_completed BOOLEAN NOT NULL DEFAULT false,
                    done_completed BOOLEAN NOT NULL DEFAULT false,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (user_id),
                    FOREIGN KEY(user_id) REFERENCES users (id)
                );
            END IF;
        END $$;
    """)
    
    # Create enum types first (if they don't exist)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE relationshiptype AS ENUM ('COUPLE', 'FAMILY', 'FRIEND_1_1', 'FRIEND_GROUP', 'OTHER');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE relationshipstatus AS ENUM ('DRAFT', 'PENDING_ACCEPTANCE', 'ACTIVE', 'DECLINED', 'REVOKED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE memberstatus AS ENUM ('INVITED', 'ACCEPTED', 'DECLINED', 'REMOVED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE memberrole AS ENUM ('OWNER', 'MEMBER');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE consentstatus AS ENUM ('DRAFT', 'ACTIVE', 'REVOKED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE inviteerole AS ENUM ('PARTNER', 'CHILD', 'FRIEND', 'FAMILY', 'OTHER');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invitestatus AS ENUM ('CREATED', 'SENT', 'OPENED', 'ACCEPTED', 'DECLINED', 'EXPIRED', 'CANCELED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE voiceenrollmentstatus AS ENUM ('STARTED', 'UPLOADED', 'COMPLETED', 'FAILED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Update relationships table (only if columns don't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='type') THEN
                ALTER TABLE relationships ADD COLUMN type relationshiptype;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='created_by_user_id') THEN
                ALTER TABLE relationships ADD COLUMN created_by_user_id VARCHAR;
            END IF;
        END $$;
    """)
    
    # Migrate existing rel_type to type (handle case where rel_type might not exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='rel_type') THEN
                UPDATE relationships 
                SET type = CASE 
                    WHEN rel_type = 'romantic' THEN 'COUPLE'::relationshiptype
                    WHEN rel_type = 'family' THEN 'FAMILY'::relationshiptype
                    WHEN rel_type = 'friend' THEN 'FRIEND_1_1'::relationshiptype
                    ELSE 'OTHER'::relationshiptype
                END
                WHERE type IS NULL;
            ELSE
                -- If rel_type doesn't exist, set default
                UPDATE relationships SET type = 'OTHER'::relationshiptype WHERE type IS NULL;
            END IF;
        END $$;
    """)
    
    # Set default for created_by_user_id
    op.execute("""
        UPDATE relationships 
        SET created_by_user_id = (
            SELECT user_id 
            FROM relationship_members 
            WHERE relationship_members.relationship_id = relationships.id 
            LIMIT 1
        )
        WHERE created_by_user_id IS NULL;
    """)
    
    # Set a default if still null (for relationships with no members)
    op.execute("UPDATE relationships SET created_by_user_id = (SELECT id FROM users LIMIT 1) WHERE created_by_user_id IS NULL")
    
    # Make type and created_by_user_id NOT NULL after migration (only if not already NOT NULL)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='type' AND is_nullable='YES') THEN
                ALTER TABLE relationships ALTER COLUMN type SET NOT NULL;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='created_by_user_id' AND is_nullable='YES') THEN
                ALTER TABLE relationships ALTER COLUMN created_by_user_id SET NOT NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints WHERE constraint_name='fk_relationships_created_by') THEN
                ALTER TABLE relationships ADD CONSTRAINT fk_relationships_created_by FOREIGN KEY (created_by_user_id) REFERENCES users (id);
            END IF;
        END $$;
    """)
    
    # Drop rel_type column since we're using type now (rel_type is now a computed property)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='rel_type') THEN
                -- Drop the column if it exists
                ALTER TABLE relationships DROP COLUMN rel_type;
            END IF;
        END $$;
    """)
    
    # Update relationship status - clean up incompatible data
    # Delete relationships with invalid status values that can't be converted to enum
    op.execute("""
        DO $$ 
        DECLARE
            invalid_rel_ids TEXT[];
        BEGIN
            -- Find relationships with invalid status values (not matching enum)
            -- Handle both VARCHAR and enum types
            SELECT ARRAY_AGG(id) INTO invalid_rel_ids
            FROM relationships 
            WHERE status::text NOT IN ('DRAFT', 'PENDING_ACCEPTANCE', 'ACTIVE', 'DECLINED', 'REVOKED');
            
            -- If there are invalid relationships, delete them
            IF invalid_rel_ids IS NOT NULL AND array_length(invalid_rel_ids, 1) > 0 THEN
                -- Delete relationship members first (foreign key constraint)
                DELETE FROM relationship_members 
                WHERE relationship_id = ANY(invalid_rel_ids);
                
                -- Delete invalid relationships
                DELETE FROM relationships 
                WHERE id = ANY(invalid_rel_ids);
                
                RAISE NOTICE 'Deleted % relationships with invalid status values', array_length(invalid_rel_ids, 1);
            END IF;
        END $$;
    """)
    
    # Convert status column to enum if it's still VARCHAR
    op.execute("""
        DO $$ 
        BEGIN
            -- Check if status column is VARCHAR and needs conversion
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='relationships' 
                AND column_name='status' 
                AND data_type = 'character varying'
            ) THEN
                -- Try to convert existing valid values
                -- Convert lowercase 'active' to 'ACTIVE' before enum conversion
                UPDATE relationships 
                SET status = 'ACTIVE' 
                WHERE LOWER(status) = 'active' AND status != 'ACTIVE';
                
                -- Convert other lowercase values
                UPDATE relationships 
                SET status = 'DRAFT' 
                WHERE LOWER(status) = 'draft' AND status != 'DRAFT';
                
                UPDATE relationships 
                SET status = 'PENDING_ACCEPTANCE' 
                WHERE LOWER(status) IN ('pending', 'pending_acceptance') 
                  AND status NOT IN ('PENDING_ACCEPTANCE', 'ACTIVE', 'DRAFT', 'DECLINED', 'REVOKED');
                
                UPDATE relationships 
                SET status = 'DECLINED' 
                WHERE LOWER(status) = 'declined' AND status != 'DECLINED';
                
                UPDATE relationships 
                SET status = 'REVOKED' 
                WHERE LOWER(status) = 'revoked' AND status != 'REVOKED';
                
                -- Drop default if present so PostgreSQL can cast column to enum (default cannot be cast automatically)
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'relationships'
                    AND column_name = 'status' AND column_default IS NOT NULL
                ) THEN
                    ALTER TABLE relationships ALTER COLUMN status DROP DEFAULT;
                END IF;
                
                -- Now convert VARCHAR column to enum type
                ALTER TABLE relationships 
                ALTER COLUMN status TYPE relationshipstatus 
                USING status::relationshipstatus;
                
                -- Restore default
                ALTER TABLE relationships ALTER COLUMN status SET DEFAULT 'ACTIVE'::relationshipstatus;
            END IF;
        END $$;
    """)
    
    # Update relationship_members table (only if columns don't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_members' AND column_name='member_status') THEN
                ALTER TABLE relationship_members ADD COLUMN member_status memberstatus;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_members' AND column_name='added_at') THEN
                ALTER TABLE relationship_members ADD COLUMN added_at TIMESTAMP WITHOUT TIME ZONE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_members' AND column_name='responded_at') THEN
                ALTER TABLE relationship_members ADD COLUMN responded_at TIMESTAMP WITHOUT TIME ZONE;
            END IF;
        END $$;
    """)
    
    # Migrate existing data
    op.execute("UPDATE relationship_members SET member_status = 'ACCEPTED'::memberstatus WHERE member_status IS NULL")
    op.execute("UPDATE relationship_members SET added_at = NOW() WHERE added_at IS NULL")
    
    # Make NOT NULL (only if currently nullable)
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_members' AND column_name='member_status' AND is_nullable='YES') THEN
                ALTER TABLE relationship_members ALTER COLUMN member_status SET NOT NULL;
            END IF;
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_members' AND column_name='added_at' AND is_nullable='YES') THEN
                ALTER TABLE relationship_members ALTER COLUMN added_at SET NOT NULL;
            END IF;
        END $$;
    """)
    
    # Role column already exists as VARCHAR, no need to change
    
    # Rename consents table to relationship_consents and update schema
    # Only rename if consents exists AND relationship_consents doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='consents') 
               AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='relationship_consents') THEN
                ALTER TABLE consents RENAME TO relationship_consents;
            END IF;
        END $$;
    """)
    
    # Drop created_at if it exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_consents' AND column_name='created_at') THEN
                ALTER TABLE relationship_consents DROP COLUMN created_at;
            END IF;
        END $$;
    """)
    
    # Update scopes column type if it exists and is String
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_consents' AND column_name='scopes' AND data_type='character varying') THEN
                ALTER TABLE relationship_consents ALTER COLUMN scopes TYPE JSONB USING scopes::jsonb;
            END IF;
        END $$;
    """)
    
    # Add new columns if they don't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_consents' AND column_name='version') THEN
                ALTER TABLE relationship_consents ADD COLUMN version VARCHAR NOT NULL DEFAULT '1';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationship_consents' AND column_name='status') THEN
                ALTER TABLE relationship_consents ADD COLUMN status consentstatus NOT NULL DEFAULT 'DRAFT';
            END IF;
        END $$;
    """)
    
    # Create voice_enrollments table (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='voice_enrollments') THEN
                CREATE TABLE voice_enrollments (
                    id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    status voiceenrollmentstatus NOT NULL,
                    audio_path VARCHAR,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(user_id) REFERENCES users (id)
                );
                CREATE INDEX ix_voice_enrollments_user_id ON voice_enrollments (user_id);
            END IF;
        END $$;
    """)
    
    # Create voice_profiles table (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='voice_profiles') THEN
                CREATE TABLE voice_profiles (
                    id VARCHAR NOT NULL,
                    user_id VARCHAR NOT NULL,
                    quality_score DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(user_id) REFERENCES users (id)
                );
                CREATE UNIQUE INDEX ix_voice_profiles_user_id ON voice_profiles (user_id);
            END IF;
        END $$;
    """)
    
    # Create relationship_invites table (only if it doesn't exist)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='relationship_invites') THEN
                CREATE TABLE relationship_invites (
                    id VARCHAR NOT NULL,
                    relationship_id VARCHAR NOT NULL,
                    inviter_user_id VARCHAR NOT NULL,
                    invitee_email VARCHAR NOT NULL,
                    invitee_user_id VARCHAR,
                    invitee_role inviteerole,
                    status invitestatus NOT NULL,
                    token_hash VARCHAR NOT NULL,
                    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    sent_at TIMESTAMP WITHOUT TIME ZONE,
                    accepted_at TIMESTAMP WITHOUT TIME ZONE,
                    declined_at TIMESTAMP WITHOUT TIME ZONE,
                    PRIMARY KEY (id),
                    FOREIGN KEY(relationship_id) REFERENCES relationships (id),
                    FOREIGN KEY(inviter_user_id) REFERENCES users (id),
                    FOREIGN KEY(invitee_user_id) REFERENCES users (id)
                );
                CREATE INDEX ix_relationship_invites_relationship_id ON relationship_invites (relationship_id);
                CREATE INDEX ix_relationship_invites_invitee_email ON relationship_invites (invitee_email);
                CREATE INDEX ix_relationship_invites_token_hash ON relationship_invites (token_hash);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop new tables
    op.drop_index(op.f('ix_relationship_invites_token_hash'), table_name='relationship_invites')
    op.drop_index(op.f('ix_relationship_invites_invitee_email'), table_name='relationship_invites')
    op.drop_index(op.f('ix_relationship_invites_relationship_id'), table_name='relationship_invites')
    op.drop_table('relationship_invites')
    
    op.drop_index(op.f('ix_voice_profiles_user_id'), table_name='voice_profiles')
    op.drop_table('voice_profiles')
    
    op.drop_index(op.f('ix_voice_enrollments_user_id'), table_name='voice_enrollments')
    op.drop_table('voice_enrollments')
    
    # Revert relationship_consents changes
    op.drop_column('relationship_consents', 'status')
    op.drop_column('relationship_consents', 'version')
    op.alter_column('relationship_consents', 'scopes', type_=sa.String(), existing_type=postgresql.JSONB)
    op.add_column('relationship_consents', sa.Column('created_at', sa.DateTime(), nullable=False))
    op.rename_table('relationship_consents', 'consents')
    
    # Revert relationship_members changes
    op.drop_column('relationship_members', 'responded_at')
    op.drop_column('relationship_members', 'added_at')
    op.drop_column('relationship_members', 'member_status')
    
    # Revert relationships changes
    op.drop_constraint('fk_relationships_created_by', 'relationships', type_='foreignkey')
    op.drop_column('relationships', 'created_by_user_id')
    op.drop_column('relationships', 'type')
    
    # Drop onboarding_progress
    op.drop_table('onboarding_progress')
    
    # Revert users changes
    op.drop_column('users', 'privacy_tier')
    op.drop_column('users', 'goals')
    op.drop_column('users', 'communication_style')
    op.drop_column('users', 'pronouns')
