#!/bin/bash
# Script to drop the rel_type column from relationships table

echo "Dropping rel_type column from relationships table..."

# Try docker-compose first
if command -v docker-compose &> /dev/null; then
    echo "Using docker-compose..."
    docker-compose exec -T postgres psql -U postgres -d project_inside << 'EOF'
ALTER TABLE relationships DROP COLUMN IF EXISTS rel_type;
SELECT 'rel_type column dropped successfully' AS result;
EOF
    if [ $? -eq 0 ]; then
        echo "✅ Successfully dropped rel_type column via docker-compose"
        exit 0
    fi
fi

# Fallback: try direct psql
echo "Trying direct psql connection..."
psql -h localhost -U postgres -d project_inside -c "ALTER TABLE relationships DROP COLUMN IF EXISTS rel_type;" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Successfully dropped rel_type column via direct psql"
    exit 0
fi

echo "❌ Failed to connect to database. Please run manually:"
echo "   docker-compose exec postgres psql -U postgres -d project_inside -c \"ALTER TABLE relationships DROP COLUMN IF EXISTS rel_type;\""
echo "   OR"
echo "   psql -h localhost -U postgres -d project_inside -c \"ALTER TABLE relationships DROP COLUMN IF EXISTS rel_type;\""
exit 1
