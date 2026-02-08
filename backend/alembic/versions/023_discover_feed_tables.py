"""Add discover_feed_items and discover_dismissals for shared Discover feed.

Revision ID: 023_discover_feed
Revises: 022_card_snapshot
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "023_discover_feed"
down_revision = "022_card_snapshot"
branch_labels = None
depends_on = None


def _table_exists(conn: sa.engine.Connection, table: str) -> bool:
    return inspect(conn).has_table(table)


def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, "discover_feed_items"):
        op.create_table(
            "discover_feed_items",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("relationship_id", sa.String(), sa.ForeignKey("relationships.id"), nullable=False, index=True),
            sa.Column("activity_template_id", sa.String(), sa.ForeignKey("activity_templates.activity_id"), nullable=False, index=True),
            sa.Column("card_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("generated_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("recommended_invitee_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_discover_feed_items_relationship_user",
            "discover_feed_items",
            ["relationship_id", "generated_by_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_discover_feed_items_relationship_invitee",
            "discover_feed_items",
            ["relationship_id", "recommended_invitee_user_id"],
            unique=False,
        )

    if not _table_exists(conn, "discover_dismissals"):
        op.create_table(
            "discover_dismissals",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("relationship_id", sa.String(), sa.ForeignKey("relationships.id"), nullable=False, index=True),
            sa.Column("discover_feed_item_id", sa.String(), sa.ForeignKey("discover_feed_items.id"), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_discover_dismissals_user_relationship",
            "discover_dismissals",
            ["user_id", "relationship_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("discover_dismissals")
    op.drop_table("discover_feed_items")
