"""Add context_summaries table for per-use-case personalization context.

Revision ID: 015_context_summaries
Revises: 014_compass_tables
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "015_context_summaries"
down_revision = "014_compass_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "context_summaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=True),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("use_case", sa.String(), nullable=False),
        sa.Column("scenario", sa.String(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_context_summaries_actor_user_id", "context_summaries", ["actor_user_id"])
    op.create_index("ix_context_summaries_relationship_id", "context_summaries", ["relationship_id"])
    op.create_index("ix_context_summaries_use_case", "context_summaries", ["use_case"])
    op.create_index("ix_context_summaries_scenario", "context_summaries", ["scenario"])
    op.create_index(
        "ix_context_summaries_relationship_use_case",
        "context_summaries",
        ["relationship_id", "use_case"],
    )
    op.create_index(
        "ix_context_summaries_actor_use_case",
        "context_summaries",
        ["actor_user_id", "use_case"],
    )


def downgrade() -> None:
    op.drop_index("ix_context_summaries_actor_use_case", table_name="context_summaries")
    op.drop_index("ix_context_summaries_relationship_use_case", table_name="context_summaries")
    op.drop_index("ix_context_summaries_scenario", table_name="context_summaries")
    op.drop_index("ix_context_summaries_use_case", table_name="context_summaries")
    op.drop_index("ix_context_summaries_relationship_id", table_name="context_summaries")
    op.drop_index("ix_context_summaries_actor_user_id", table_name="context_summaries")
    op.drop_table("context_summaries")
