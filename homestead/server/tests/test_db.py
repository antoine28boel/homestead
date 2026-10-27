"""Tests for the database schema and migrations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from homestead_server.db import make_engine, make_sessions, migrate
from homestead_server.orm import Base, TaskStateRow


def test_migrations_match_tables(tmp_path: Path) -> None:
    """The migrations build exactly the tables the code declares."""
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate(engine)
    migrate(engine)  # Running again changes nothing.
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "render_as_batch": True}
        )
        assert compare_metadata(context, Base.metadata) == []
    assert "alembic_version" in inspect(engine).get_table_names()


def test_times_are_stored_in_utc(tmp_path: Path) -> None:
    """A local time comes back as the same instant, in UTC."""
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate(engine)
    sessions = make_sessions(engine)
    local = datetime(2027, 3, 20, 9, 0, tzinfo=timezone(timedelta(hours=1)))
    with sessions() as session:
        session.add(TaskStateRow(uid="a.b", status="done", at=local))
        session.commit()
    with sessions() as session:
        stored = session.get(TaskStateRow, "a.b")
        assert stored is not None
        assert stored.at == local
        assert stored.at.tzinfo is UTC
