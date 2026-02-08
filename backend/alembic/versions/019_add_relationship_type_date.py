"""Add DATE to relationshiptype enum.

Revision ID: 019_relationship_type_date
Revises: 018_dyad_planned_memory
Create Date: 2026-01-30

"""
from alembic import op

revision = "019_relationship_type_date"
down_revision = "018_dyad_planned_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add DATE to relationshiptype enum (idempotent: ignore if already present)
    op.execute("""
        DO $$
        BEGIN
            ALTER TYPE relationshiptype ADD VALUE 'DATE';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
    """)


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value easily; leave DATE in place.
    pass
