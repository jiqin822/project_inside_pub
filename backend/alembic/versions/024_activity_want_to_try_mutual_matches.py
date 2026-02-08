"""Add activity_want_to_try and activity_mutual_matches for Want to try / mutual match.

Revision ID: 024_want_to_try
Revises: 023_discover_feed
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "024_want_to_try"
down_revision = "023_discover_feed"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :name"
        ),
        {"name": table_name},
    )
    return r.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "activity_want_to_try"):
        op.create_table(
            "activity_want_to_try",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("relationship_id", sa.String(), sa.ForeignKey("relationships.id"), nullable=False, index=True),
            sa.Column("discover_feed_item_id", sa.String(), sa.ForeignKey("discover_feed_items.id"), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_activity_want_to_try_feed_item",
            "activity_want_to_try",
            ["discover_feed_item_id"],
            unique=False,
        )

    if not _table_exists(conn, "activity_mutual_matches"):
        op.create_table(
            "activity_mutual_matches",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("relationship_id", sa.String(), sa.ForeignKey("relationships.id"), nullable=False, index=True),
            sa.Column("discover_feed_item_id", sa.String(), sa.ForeignKey("discover_feed_items.id"), nullable=False, index=True),
            sa.Column("user_a_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("user_b_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("user_a_response", sa.String(), nullable=False, server_default="pending"),  # pending | accept | decline
            sa.Column("user_b_response", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_activity_mutual_matches_user_a",
            "activity_mutual_matches",
            ["user_a_id", "user_a_response"],
            unique=False,
        )
        op.create_index(
            "ix_activity_mutual_matches_user_b",
            "activity_mutual_matches",
            ["user_b_id", "user_b_response"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("activity_mutual_matches")
    op.drop_table("activity_want_to_try")
