"""Phase B: append-only ``repo_star_snapshots`` + ``ingest_runs`` audit log.

Revision ID: 0002_phase_b_snapshots
Revises: 0001_initial
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_phase_b_snapshots"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repo_star_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repo_id",
            sa.Integer(),
            sa.ForeignKey("repos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("forks", sa.Integer(), nullable=False),
    )
    op.create_index("ix_repo_star_snapshots_repo_id", "repo_star_snapshots", ["repo_id"])
    op.create_index("idx_snap_repo_time", "repo_star_snapshots", ["repo_id", "captured_at"])

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("repos_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("api_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("etag_hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_msg", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_ingest_runs_started_at", "ingest_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_ingest_runs_started_at", table_name="ingest_runs")
    op.drop_table("ingest_runs")

    op.drop_index("idx_snap_repo_time", table_name="repo_star_snapshots")
    op.drop_index("ix_repo_star_snapshots_repo_id", table_name="repo_star_snapshots")
    op.drop_table("repo_star_snapshots")
