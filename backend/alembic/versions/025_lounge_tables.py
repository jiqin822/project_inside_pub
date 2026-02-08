"""Add lounge tables (rooms, members, messages, kai context, events).

Revision ID: 025_lounge
Revises: 024_want_to_try
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "025_lounge"
down_revision = "024_want_to_try"
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
    if _table_exists(conn, "lounge_rooms"):
        return
    op.create_table(
        "lounge_rooms",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "lounge_members",
        sa.Column("room_id", sa.String(), sa.ForeignKey("lounge_rooms.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("invited_by_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.PrimaryKeyConstraint("room_id", "user_id"),
    )
    op.create_index("ix_lounge_members_user_id", "lounge_members", ["user_id"], unique=False)

    op.create_table(
        "lounge_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("room_id", sa.String(), sa.ForeignKey("lounge_rooms.id"), nullable=False, index=True),
        sa.Column("sender_user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True, index=True),  # None = Kai
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(), nullable=False, server_default="public", index=True),
        sa.Column("sequence", sa.Integer(), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lounge_messages_room_sequence", "lounge_messages", ["room_id", "sequence"], unique=False)

    op.create_table(
        "lounge_kai_context",
        sa.Column("room_id", sa.String(), sa.ForeignKey("lounge_rooms.id"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("extracted_facts", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("room_id"),
    )

    op.create_table(
        "lounge_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("room_id", sa.String(), sa.ForeignKey("lounge_rooms.id"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False, index=True),
        sa.Column("event_type", sa.String(), nullable=False, index=True),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lounge_events_room_sequence", "lounge_events", ["room_id", "sequence"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lounge_events_room_sequence", table_name="lounge_events")
    op.drop_table("lounge_events")
    op.drop_table("lounge_kai_context")
    op.drop_index("ix_lounge_messages_room_sequence", table_name="lounge_messages")
    op.drop_table("lounge_messages")
    op.drop_index("ix_lounge_members_user_id", table_name="lounge_members")
    op.drop_table("lounge_members")
    op.drop_table("lounge_rooms")
