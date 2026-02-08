"""Add missing columns to kai_user_preferences (kind, source, room_id, created_at).

The table may have been created with only id, user_id, content. Adds any missing columns.
Revision ID: 033_kai_prefs_missing
Revises: 032_kai_prefs_content
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "033_kai_prefs_missing"
down_revision = "032_kai_prefs_content"
branch_labels = None
depends_on = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c LIMIT 1"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.fetchone() is not None


def _index_exists(connection, index_name: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = 'public' AND indexname = :name LIMIT 1"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    t = "kai_user_preferences"

    if not _column_exists(conn, t, "kind"):
        op.add_column(t, sa.Column("kind", sa.String(), nullable=True, index=True))
        op.execute("UPDATE kai_user_preferences SET kind = 'preference' WHERE kind IS NULL")
        op.alter_column(t, "kind", existing_type=sa.String(), nullable=False)

    if not _column_exists(conn, t, "source"):
        op.add_column(t, sa.Column("source", sa.String(), nullable=True, index=True))
        op.execute("UPDATE kai_user_preferences SET source = 'public' WHERE source IS NULL")
        op.alter_column(t, "source", existing_type=sa.String(), nullable=False)

    if not _column_exists(conn, t, "room_id"):
        op.add_column(
            t,
            sa.Column("room_id", sa.String(), sa.ForeignKey("lounge_rooms.id"), nullable=True, index=True),
        )

    if not _column_exists(conn, t, "created_at"):
        op.add_column(
            t,
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not _index_exists(conn, "ix_kai_user_preferences_user_created"):
        op.create_index(
            "ix_kai_user_preferences_user_created",
            t,
            ["user_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    t = "kai_user_preferences"
    if _index_exists(conn, "ix_kai_user_preferences_user_created"):
        op.drop_index("ix_kai_user_preferences_user_created", table_name=t)
    if _column_exists(conn, t, "created_at"):
        op.drop_column(t, "created_at")
    if _column_exists(conn, t, "room_id"):
        op.drop_column(t, "room_id")
    if _column_exists(conn, t, "source"):
        op.drop_column(t, "source")
    if _column_exists(conn, t, "kind"):
        op.drop_column(t, "kind")
