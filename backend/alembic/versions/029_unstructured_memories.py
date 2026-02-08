"""Add unstructured_memories table for Kai insights (Compass).

Revision ID: 029_unstructured_memories
Revises: 028_compass_processed_at
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "029_unstructured_memories"
down_revision = "028_compass_processed_at"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    """Return True if the table exists (avoids failing the transaction)."""
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name LIMIT 1"
        ),
        {"name": table_name},
    )
    return result.fetchone() is not None


def _index_exists(connection, index_name: str) -> bool:
    """Return True if the given index exists."""
    result = connection.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'public' AND indexname = :name LIMIT 1"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    connection = op.get_bind()
    if _table_exists(connection, "unstructured_memories"):
        # Table already exists; ensure indexes exist.
        if not _index_exists(connection, "ix_unstructured_memories_owner_created"):
            op.create_index(
                "ix_unstructured_memories_owner_created",
                "unstructured_memories",
                ["owner_user_id", "created_at"],
                unique=False,
            )
        if not _index_exists(connection, "ix_unstructured_memories_relationship_created"):
            op.create_index(
                "ix_unstructured_memories_relationship_created",
                "unstructured_memories",
                ["relationship_id", "created_at"],
                unique=False,
            )
        return
    op.create_table(
        "unstructured_memories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("relationship_id", sa.String(), sa.ForeignKey("relationships.id"), nullable=True, index=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_unstructured_memories_owner_created",
        "unstructured_memories",
        ["owner_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_unstructured_memories_relationship_created",
        "unstructured_memories",
        ["relationship_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_unstructured_memories_relationship_created", table_name="unstructured_memories")
    op.drop_index("ix_unstructured_memories_owner_created", table_name="unstructured_memories")
    op.drop_table("unstructured_memories")
