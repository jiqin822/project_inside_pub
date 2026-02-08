"""Activity invites, planned_activities, dyad_activity_history notes/memory_urls.

Revision ID: 016_activity_invites_planned
Revises: 015_context_summaries
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "016_activity_invites_planned"
down_revision = "015_context_summaries"
branch_labels = None
depends_on = None


def _table_exists(conn: sa.engine.Connection, name: str) -> bool:
    return inspect(conn).has_table(name)


def _column_exists(conn: sa.engine.Connection, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(conn).get_columns(table)]


def upgrade() -> None:
    conn = op.get_bind()

    # activity_invites (idempotent: skip if table already exists)
    if not _table_exists(conn, "activity_invites"):
        op.create_table(
            "activity_invites",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("relationship_id", sa.String(), nullable=False),
            sa.Column("activity_template_id", sa.String(), nullable=False),
            sa.Column("from_user_id", sa.String(), nullable=False),
            sa.Column("to_user_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("responded_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
            sa.ForeignKeyConstraint(["activity_template_id"], ["activity_templates.activity_id"]),
            sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_activity_invites_to_user_id_status", "activity_invites", ["to_user_id", "status"])
        op.create_index("ix_activity_invites_relationship_id", "activity_invites", ["relationship_id"])

    # planned_activities (idempotent: skip if table already exists)
    if not _table_exists(conn, "planned_activities"):
        op.create_table(
            "planned_activities",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("relationship_id", sa.String(), nullable=False),
            sa.Column("activity_template_id", sa.String(), nullable=False),
            sa.Column("initiator_user_id", sa.String(), nullable=False),
            sa.Column("invitee_user_id", sa.String(), nullable=False),
            sa.Column("invite_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="planned"),
            sa.Column("agreed_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("notes_text", sa.Text(), nullable=True),
            sa.Column("memory_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
            sa.ForeignKeyConstraint(["activity_template_id"], ["activity_templates.activity_id"]),
            sa.ForeignKeyConstraint(["initiator_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["invitee_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["invite_id"], ["activity_invites.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_planned_activities_initiator_status", "planned_activities", ["initiator_user_id", "status"])
        op.create_index("ix_planned_activities_invitee_status", "planned_activities", ["invitee_user_id", "status"])
        op.create_index("ix_planned_activities_relationship_id", "planned_activities", ["relationship_id"])

    # dyad_activity_history: add notes_text and memory_urls (idempotent: skip if column exists)
    if not _column_exists(conn, "dyad_activity_history", "notes_text"):
        op.add_column("dyad_activity_history", sa.Column("notes_text", sa.Text(), nullable=True))
    if not _column_exists(conn, "dyad_activity_history", "memory_urls"):
        op.add_column("dyad_activity_history", sa.Column("memory_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    # dyad_activity_history: drop columns only if they exist
    if _column_exists(conn, "dyad_activity_history", "memory_urls"):
        op.drop_column("dyad_activity_history", "memory_urls")
    if _column_exists(conn, "dyad_activity_history", "notes_text"):
        op.drop_column("dyad_activity_history", "notes_text")
    if _table_exists(conn, "planned_activities"):
        op.drop_index("ix_planned_activities_relationship_id", table_name="planned_activities")
        op.drop_index("ix_planned_activities_invitee_status", table_name="planned_activities")
        op.drop_index("ix_planned_activities_initiator_status", table_name="planned_activities")
        op.drop_table("planned_activities")
    if _table_exists(conn, "activity_invites"):
        op.drop_index("ix_activity_invites_relationship_id", table_name="activity_invites")
        op.drop_index("ix_activity_invites_to_user_id_status", table_name="activity_invites")
        op.drop_table("activity_invites")
