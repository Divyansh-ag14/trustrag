"""add knowledge gaps table

Revision ID: e1f2a3b4c5d6
Revises: d8a1b3f5e901
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d8a1b3f5e901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_gaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("queries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("missing_topic", sa.Text(), nullable=True),
        sa.Column("weak_sources", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("occurrences", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'open'"), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_knowledge_gaps_workspace", "knowledge_gaps", ["workspace_id"])
    op.create_index("idx_knowledge_gaps_status", "knowledge_gaps", ["workspace_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_knowledge_gaps_status")
    op.drop_index("idx_knowledge_gaps_workspace")
    op.drop_table("knowledge_gaps")
