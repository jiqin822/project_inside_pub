"""Add kai_user_preferences table for per-user feedback/preference memory.

Revision ID: 027_kai_user_prefs
Revises: 026_lounge_sender_null
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "027_kai_user_prefs"
down_revision = "026_lounge_sender_null"
branch_labels = None
depends_on = None


def _table_exists(connection) -> bool:
    """Return True if kai_user_preferences table exists (avoids failing the transaction)."""
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'kai_user_preferences' LIMIT 1"
        )
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
    if _table_exists(connection):
        # Table already exists (e.g. created manually or previous partial run); ensure index.
        if not _index_exists(connection, "ix_kai_user_preferences_user_created"):
            op.create_index(
                "ix_kai_user_preferences_user_created",
                "kai_user_preferences",
                ["user_id", "created_at"],
                unique=False,
            )
        return
    op.create_table(
        "kai_user_preferences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, index=True),
        sa.Column("source", sa.String(), nullable=False, index=True),
        sa.Column("room_id", sa.String(), sa.ForeignKey("lounge_rooms.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kai_user_preferences_user_created",
        "kai_user_preferences",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_kai_user_preferences_user_created", table_name="kai_user_preferences")
    op.drop_table("kai_user_preferences")
