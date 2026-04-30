"""SQLAlchemy ORM models for goodailist-clone."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

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

    @property
    def full_name(self) -> str:
        return f"{self.org}/{self.name}"

    @property
    def stars_1d_delta(self) -> int:
        return self.stars - self.stars_1d_ago

    @property
    def stars_7d_delta(self) -> int:
        return self.stars - self.stars_7d_ago
