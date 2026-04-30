"""Phase A baseline: ``repos`` table.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars_1d_ago", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars_7d_ago", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("forks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.Date(), nullable=False),
    )
    op.create_index("ix_repos_org", "repos", ["org"])
    op.create_index("ix_repos_name", "repos", ["name"])
    op.create_index("ix_repos_category", "repos", ["category"])


def downgrade() -> None:
    op.drop_index("ix_repos_category", table_name="repos")
    op.drop_index("ix_repos_name", table_name="repos")
    op.drop_index("ix_repos_org", table_name="repos")
    op.drop_table("repos")
