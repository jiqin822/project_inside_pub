-- Quick fix: Drop rel_type column since it's no longer used
-- The type column is now used instead, and rel_type is a computed property

DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='relationships' AND column_name='rel_type') THEN
        ALTER TABLE relationships DROP COLUMN rel_type;
        RAISE NOTICE 'Dropped rel_type column';
    ELSE
        RAISE NOTICE 'rel_type column does not exist';
    END IF;
END $$;
