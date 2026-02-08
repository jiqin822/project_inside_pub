-- Script to delete user with email 'c@g.com' and all related records
-- Run with: psql -U postgres -d project_inside -f scripts/delete_user.sql

DO $$
DECLARE
    target_user_id VARCHAR;
    deleted_count INTEGER;
BEGIN
    -- Find the user
    SELECT id INTO target_user_id FROM users WHERE email = 'c@g.com';
    
    IF target_user_id IS NULL THEN
        RAISE NOTICE 'User with email c@g.com not found.';
        RETURN;
    END IF;
    
    RAISE NOTICE 'Found user: % (email: c@g.com)', target_user_id;
    RAISE NOTICE 'Deleting related records...';
    
    -- Delete in order (child tables first)
    
    -- 1. Market: Transactions (via wallets)
    DELETE FROM transactions 
    WHERE wallet_id IN (
        SELECT id FROM wallets 
        WHERE issuer_id = target_user_id OR holder_id = target_user_id
    );
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % transactions', deleted_count;
    
    -- 2. Market: Wallets
    DELETE FROM wallets 
    WHERE issuer_id = target_user_id OR holder_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % wallets', deleted_count;
    
    -- 3. Market: Market Items
    DELETE FROM market_items WHERE issuer_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % market items', deleted_count;
    
    -- 4. Market: Economy Settings
    DELETE FROM economy_settings WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % economy settings', deleted_count;
    
    -- 5. Love Map: Relationship Map Progress
    DELETE FROM relationship_map_progress 
    WHERE observer_id = target_user_id OR subject_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % relationship map progress records', deleted_count;
    
    -- 6. Love Map: User Specs
    DELETE FROM user_specs WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % user specs', deleted_count;
    
    -- 7. Events: Poke Events
    DELETE FROM poke_events 
    WHERE sender_id = target_user_id OR receiver_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % poke events', deleted_count;
    
    -- 8. Sessions: Session Participants
    DELETE FROM session_participants WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % session participants', deleted_count;
    
    -- 9. Sessions: Sessions (where user is creator)
    DELETE FROM sessions WHERE created_by_user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % sessions', deleted_count;
    
    -- 10. Invites: Relationship Invites
    DELETE FROM relationship_invites 
    WHERE inviter_user_id = target_user_id OR invitee_user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % relationship invites', deleted_count;
    
    -- 11. Relationships: Relationship Members
    DELETE FROM relationship_members WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % relationship memberships', deleted_count;
    
    -- 12. Relationships: Relationships (where user is creator)
    -- First delete ALL relationship_members for these relationships (not just the target user)
    DELETE FROM relationship_members 
    WHERE relationship_id IN (
        SELECT id FROM relationships WHERE created_by_user_id = target_user_id
    );
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % relationship memberships for relationships where user was creator', deleted_count;
    
    -- Then delete related records for these relationships
    DELETE FROM poke_events 
    WHERE relationship_id IN (
        SELECT id FROM relationships WHERE created_by_user_id = target_user_id
    );
    
    DELETE FROM relationship_invites 
    WHERE relationship_id IN (
        SELECT id FROM relationships WHERE created_by_user_id = target_user_id
    );
    
    DELETE FROM sessions 
    WHERE relationship_id IN (
        SELECT id FROM relationships WHERE created_by_user_id = target_user_id
    );
    
    -- Now delete the relationships themselves
    DELETE FROM relationships WHERE created_by_user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % relationships (where user was creator)', deleted_count;
    
    -- 13. Voice: Voice Enrollments
    DELETE FROM voice_enrollments WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % voice enrollment records', deleted_count;
    
    -- 14. Voice: Voice Profiles
    DELETE FROM voice_profiles WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % voice profile records', deleted_count;
    
    -- 15. Onboarding: Onboarding Progress
    DELETE FROM onboarding_progress WHERE user_id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted % onboarding progress records', deleted_count;
    
    -- 16. Finally: Delete the user
    DELETE FROM users WHERE id = target_user_id;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE '  Deleted user';
    
    RAISE NOTICE 'Successfully deleted user c@g.com (ID: %) and all related records.', target_user_id;
    
END $$;
