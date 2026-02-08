"""Clear Resemblyzer embeddings for TitaNet migration

This migration clears all existing voice embeddings that were computed using
Resemblyzer (256-dim). The system will re-compute embeddings using TitaNet
(192-dim) on next use from the stored voice_sample_base64.

Revision ID: 013_clear_resemblyzer
Revises: 012_add_voice_embedding_json
Create Date: 2026-01-29 10:00:00.000000

"""
from alembic import op


revision = "013_clear_resemblyzer"
down_revision = "012_add_voice_embedding_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Clear all voice embeddings so they get recomputed with TitaNet."""
    op.execute(
        """
        UPDATE voice_profiles
        SET voice_embedding_json = NULL
        WHERE voice_embedding_json IS NOT NULL;
        """
    )


def downgrade() -> None:
    """No downgrade possible - embeddings must be recomputed manually."""
    pass
