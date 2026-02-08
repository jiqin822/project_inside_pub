"""Insider Compass tables (events, memories, portraits, loops, activity_templates, dyad_activity_history)

Revision ID: 014_compass_tables
Revises: 013_clear_resemblyzer
Create Date: 2026-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "014_compass_tables"
down_revision = "013_clear_resemblyzer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # compass_events
    op.create_table(
        "compass_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("privacy_scope", sa.String(), nullable=False, server_default="private"),
        sa.Column("source", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_compass_events_actor_user_id", "compass_events", ["actor_user_id"])
    op.create_index("ix_compass_events_relationship_id", "compass_events", ["relationship_id"])
    op.create_index("ix_compass_events_source", "compass_events", ["source"])
    op.create_index("ix_compass_events_actor_created", "compass_events", ["actor_user_id", "created_at"])
    op.create_index("ix_compass_events_relationship_created", "compass_events", ["relationship_id", "created_at"])
    op.create_index("ix_compass_events_source_created", "compass_events", ["source", "created_at"])

    # memories
    op.create_table(
        "memories",
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
        sa.Column("memory_type", sa.String(), nullable=False),
        sa.Column("canonical_key", sa.String(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(), nullable=False, server_default="hypothesis"),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("memory_id"),
    )
    op.create_index("ix_memories_owner_user_id", "memories", ["owner_user_id"])
    op.create_index("ix_memories_relationship_id", "memories", ["relationship_id"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_status", "memories", ["status"])
    op.create_index("ix_memories_canonical_key", "memories", ["canonical_key"])
    op.create_index("ix_memories_owner_relationship", "memories", ["owner_user_id", "relationship_id"])
    op.create_index("ix_memories_canonical_owner", "memories", ["canonical_key", "owner_user_id"])

    # person_portraits
    op.create_table(
        "person_portraits",
        sa.Column("portrait_id", sa.String(), nullable=False),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False, server_default="private"),
        sa.Column("portrait_text", sa.Text(), nullable=True),
        sa.Column("portrait_facets_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("portrait_id"),
    )
    op.create_index("ix_person_portraits_owner_user_id", "person_portraits", ["owner_user_id"])
    op.create_index("ix_person_portraits_relationship_id", "person_portraits", ["relationship_id"])
    op.create_index("ix_person_portraits_owner_relationship", "person_portraits", ["owner_user_id", "relationship_id"])

    # dyad_portraits
    op.create_table(
        "dyad_portraits",
        sa.Column("dyad_portrait_id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=False),
        sa.Column("portrait_text", sa.Text(), nullable=True),
        sa.Column("facets_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("dyad_portrait_id"),
    )
    op.create_index("ix_dyad_portraits_relationship_id", "dyad_portraits", ["relationship_id"])

    # relationship_loops
    op.create_table(
        "relationship_loops",
        sa.Column("loop_id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("trigger_signals_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("meanings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("patterns_by_person_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("heat_signature_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("repair_attempts_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_interruptions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(), nullable=False, server_default="hypothesis"),
        sa.Column("evidence_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.PrimaryKeyConstraint("loop_id"),
    )
    op.create_index("ix_relationship_loops_relationship_id", "relationship_loops", ["relationship_id"])
    op.create_index("ix_relationship_loops_status", "relationship_loops", ["status"])

    # activity_templates
    op.create_table(
        "activity_templates",
        sa.Column("activity_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("relationship_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("age_range", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("vibe_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("personalization_slots", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("steps_markdown_template", sa.Text(), nullable=True),
        sa.Column("variants", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("safety_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("activity_id"),
    )
    op.create_index("ix_activity_templates_is_active", "activity_templates", ["is_active"])

    # dyad_activity_history
    op.create_table(
        "dyad_activity_history",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("relationship_id", sa.String(), nullable=False),
        sa.Column("activity_template_id", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("outcome_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["relationship_id"], ["relationships.id"]),
        sa.ForeignKeyConstraint(["activity_template_id"], ["activity_templates.activity_id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dyad_activity_history_relationship_id", "dyad_activity_history", ["relationship_id"])
    op.create_index("ix_dyad_activity_history_activity_template_id", "dyad_activity_history", ["activity_template_id"])
    op.create_index("ix_dyad_activity_history_actor_user_id", "dyad_activity_history", ["actor_user_id"])
    op.create_index("ix_dyad_activity_history_relationship_started", "dyad_activity_history", ["relationship_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_dyad_activity_history_relationship_started", table_name="dyad_activity_history")
    op.drop_index("ix_dyad_activity_history_actor_user_id", table_name="dyad_activity_history")
    op.drop_index("ix_dyad_activity_history_activity_template_id", table_name="dyad_activity_history")
    op.drop_index("ix_dyad_activity_history_relationship_id", table_name="dyad_activity_history")
    op.drop_table("dyad_activity_history")
    op.drop_index("ix_activity_templates_is_active", table_name="activity_templates")
    op.drop_table("activity_templates")
    op.drop_index("ix_relationship_loops_status", table_name="relationship_loops")
    op.drop_index("ix_relationship_loops_relationship_id", table_name="relationship_loops")
    op.drop_table("relationship_loops")
    op.drop_index("ix_dyad_portraits_relationship_id", table_name="dyad_portraits")
    op.drop_table("dyad_portraits")
    op.drop_index("ix_person_portraits_owner_relationship", table_name="person_portraits")
    op.drop_index("ix_person_portraits_relationship_id", table_name="person_portraits")
    op.drop_index("ix_person_portraits_owner_user_id", table_name="person_portraits")
    op.drop_table("person_portraits")
    op.drop_index("ix_memories_canonical_owner", table_name="memories")
    op.drop_index("ix_memories_owner_relationship", table_name="memories")
    op.drop_index("ix_memories_canonical_key", table_name="memories")
    op.drop_index("ix_memories_status", table_name="memories")
    op.drop_index("ix_memories_memory_type", table_name="memories")
    op.drop_index("ix_memories_relationship_id", table_name="memories")
    op.drop_index("ix_memories_owner_user_id", table_name="memories")
    op.drop_table("memories")
    op.drop_index("ix_compass_events_source_created", table_name="compass_events")
    op.drop_index("ix_compass_events_relationship_created", table_name="compass_events")
    op.drop_index("ix_compass_events_actor_created", table_name="compass_events")
    op.drop_index("ix_compass_events_source", table_name="compass_events")
    op.drop_index("ix_compass_events_relationship_id", table_name="compass_events")
    op.drop_index("ix_compass_events_actor_user_id", table_name="compass_events")
    op.drop_table("compass_events")
