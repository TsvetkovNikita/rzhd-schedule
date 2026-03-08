from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.models import TrainRow


class Base(DeclarativeBase):
    pass


class ScheduleImportBatchORM(Base):
    __tablename__ = "schedule_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="yandex")
    station_code: Mapped[str] = mapped_column(String(64), nullable=False)
    station_system: Mapped[str] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    rows: Mapped[list["ScheduleImportRowORM"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScheduleImportRowORM.sort_time",
    )


class ScheduleImportRowORM(Base):
    __tablename__ = "schedule_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "source_key", name="uq_schedule_import_rows_batch_source_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    train_uid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transport_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    number: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    arrival: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    departure: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    batch: Mapped[ScheduleImportBatchORM] = relationship(back_populates="rows")

    def to_train_row(self) -> TrainRow:
        return TrainRow(
            number=self.number,
            title=self.title,
            arrival=self.arrival,
            departure=self.departure,
            source_key=self.source_key,
            train_uid=self.train_uid,
            transport_type=self.transport_type,
        )
