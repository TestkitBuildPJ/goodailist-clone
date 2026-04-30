"""SQLAlchemy ORM models for goodailist-clone."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Repo(Base):
    """A single GitHub repository tracked by goodailist."""

    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    stars_1d_ago: Mapped[int] = mapped_column(Integer, default=0)
    stars_7d_ago: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[date] = mapped_column(Date)
    updated_at: Mapped[date] = mapped_column(Date)

    snapshots: Mapped[list[RepoStarSnapshot]] = relationship(
        back_populates="repo",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def full_name(self) -> str:
        return f"{self.org}/{self.name}"

    @property
    def stars_1d_delta(self) -> int:
        return self.stars - self.stars_1d_ago

    @property
    def stars_7d_delta(self) -> int:
        return self.stars - self.stars_7d_ago


class RepoStarSnapshot(Base):
    """Append-only time-series of star/fork counts per repo (Phase B).

    Phase A approximates the cumulative chart from 4 anchor points stored
    on :class:`Repo`.  Phase B writes one row here per cron tick so the
    chart can render real history.
    """

    __tablename__ = "repo_star_snapshots"
    __table_args__ = (Index("idx_snap_repo_time", "repo_id", "captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    stars: Mapped[int] = mapped_column(Integer)
    forks: Mapped[int] = mapped_column(Integer)

    repo: Mapped[Repo] = relationship(back_populates="snapshots")


class IngestRun(Base):
    """Audit log entry for one execution of the ingest cron.

    Created at job start with ``status='running'`` and finalized at end.
    Crashed runs leave dangling ``running`` rows; the scheduler reconciles
    them to ``failed`` on next startup.
    """

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    repos_updated: Mapped[int] = mapped_column(Integer, default=0)
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    etag_hits: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)
