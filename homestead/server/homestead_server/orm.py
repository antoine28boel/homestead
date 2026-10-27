"""Database tables. Every season stays in the database, year after year."""

from __future__ import annotations

from datetime import UTC, date, datetime
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    Dialect,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .const import (
    STAGE_FINISHED,
    STAGE_GROWING,
    STAGE_HARVESTING,
    STAGE_PLANNED,
    STAGE_SOWN,
    STAGE_TRANSPLANTED,
)


def new_id() -> str:
    """Random identifier, stable across renames."""
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Current time, timezone-aware."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Stored in UTC without offset, as SQLite has none; read back aware."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Convert to naive UTC."""
        if value is None:
            return None
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        """Mark as UTC."""
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    """Base of every table."""


class GardenRow(Base):
    """The garden itself (one row)."""

    __tablename__ = "garden"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(100))
    last_frost: Mapped[str] = mapped_column(String(5))
    """Average last frost of spring, MM-DD."""
    first_frost: Mapped[str] = mapped_column(String(5))
    """Average first frost of autumn, MM-DD."""


class SpaceRow(Base):
    """A bed, a raised bed, a greenhouse, pots…"""

    __tablename__ = "space"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    frost_shift: Mapped[int | None] = mapped_column(Integer)
    """Weeks gained on frost; None means the default of the type."""
    area: Mapped[float | None] = mapped_column(Float)
    """Square metres."""
    sort: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# Day each stage was reached, by stage.
STAGE_COLUMNS = {
    STAGE_SOWN: "sown_on",
    STAGE_TRANSPLANTED: "transplanted_on",
    STAGE_GROWING: "growing_on",
    STAGE_HARVESTING: "harvesting_on",
    STAGE_FINISHED: "finished_on",
}


class PlantingRow(Base):
    """One crop in one space, for one season."""

    __tablename__ = "planting"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    season: Mapped[int] = mapped_column(Integer, index=True)
    space_id: Mapped[str | None] = mapped_column(
        ForeignKey("space.id", ondelete="SET NULL")
    )
    species: Mapped[str] = mapped_column(String(50), index=True)
    variety: Mapped[str] = mapped_column(String(100), default="")
    method: Mapped[str] = mapped_column(String(20))
    window: Mapped[int] = mapped_column(Integer, default=0)
    quantity: Mapped[int | None] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(20), default=STAGE_PLANNED)
    sown_on: Mapped[date | None] = mapped_column(Date)
    transplanted_on: Mapped[date | None] = mapped_column(Date)
    growing_on: Mapped[date | None] = mapped_column(Date)
    harvesting_on: Mapped[date | None] = mapped_column(Date)
    finished_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    journal: Mapped[list[JournalRow]] = relationship(
        back_populates="planting", cascade="all, delete-orphan", passive_deletes=True
    )
    harvests: Mapped[list[HarvestRow]] = relationship(
        back_populates="planting", cascade="all, delete-orphan", passive_deletes=True
    )

    def stage_dates(self) -> dict[str, date]:
        """Day each stage was reached."""
        return {
            stage: day
            for stage, column in STAGE_COLUMNS.items()
            if (day := getattr(self, column)) is not None
        }


class JournalRow(Base):
    """Something done or seen: watering, feeding, treatment, observation."""

    __tablename__ = "journal"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    planting_id: Mapped[str | None] = mapped_column(
        ForeignKey("planting.id", ondelete="CASCADE"), index=True
    )
    space_id: Mapped[str | None] = mapped_column(
        ForeignKey("space.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    day: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    planting: Mapped[PlantingRow | None] = relationship(back_populates="journal")


class HarvestRow(Base):
    """A harvest, weighed or counted."""

    __tablename__ = "harvest"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    planting_id: Mapped[str] = mapped_column(
        ForeignKey("planting.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    planting: Mapped[PlantingRow] = relationship(back_populates="harvests")


class TaskStateRow(Base):
    """A generated task that was ticked or removed."""

    __tablename__ = "task_state"

    uid: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(10))
    """done or dismissed."""
    summary: Mapped[str] = mapped_column(String(255), default="")
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class TodoItemRow(Base):
    """An item the gardener added to the to-do list."""

    __tablename__ = "todo_item"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    summary: Mapped[str] = mapped_column(String(255))
    due: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
