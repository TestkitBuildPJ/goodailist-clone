"""Verify Alembic migrations can upgrade-then-downgrade round-trip cleanly."""

from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _alembic(cmd: list[str], db_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", "-m", "alembic", *cmd],
        cwd=PROJECT_ROOT,
        env={"GOODAILIST_DB_URL": f"sqlite:///{db_path}", "PATH": _path_env()},
        capture_output=True,
        text=True,
        check=False,
    )


def _path_env() -> str:
    import os

    return os.environ.get("PATH", "/usr/bin:/bin")


def test_alembic_upgrade_creates_three_tables(tmp_path: Path) -> None:
    """Running ``alembic upgrade head`` should create all 3 tables."""
    db = tmp_path / "test.db"
    result = _alembic(["upgrade", "head"], db)
    assert result.returncode == 0, result.stderr

    import sqlite3

    conn = sqlite3.connect(db)
    try:
        names = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert {"repos", "repo_star_snapshots", "ingest_runs"} <= names


def test_alembic_downgrade_round_trip(tmp_path: Path) -> None:
    """``upgrade head`` → ``downgrade base`` → ``upgrade head`` round-trips cleanly."""
    db = tmp_path / "test.db"
    assert _alembic(["upgrade", "head"], db).returncode == 0
    assert _alembic(["downgrade", "base"], db).returncode == 0
    assert _alembic(["upgrade", "head"], db).returncode == 0
