from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from db.models import ScheduleImportBatchORM, ScheduleImportRowORM
from core.models import TrainRow


class ScheduleImportRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_batch(
        self,
        *,
        source: str,
        station_code: str,
        station_system: str,
        timezone: str,
        window_start: datetime,
        window_end: datetime,
        imported_at: datetime,
        status: str,
        row_count: int,
        request_payload: Optional[dict[str, Any]],
        error_message: Optional[str],
    ) -> ScheduleImportBatchORM:
        batch = ScheduleImportBatchORM(
            source=source,
            station_code=station_code,
            station_system=station_system,
            timezone=timezone,
            window_start=window_start,
            window_end=window_end,
            imported_at=imported_at,
            status=status,
            row_count=row_count,
            request_payload=request_payload,
            error_message=error_message,
        )
        self.session.add(batch)
        self.session.flush()
        return batch

    def get_latest_success_batch(self) -> Optional[ScheduleImportBatchORM]:
        stmt = (
            select(ScheduleImportBatchORM)
            .where(ScheduleImportBatchORM.status == "success")
            .options(selectinload(ScheduleImportBatchORM.rows))
            .order_by(desc(ScheduleImportBatchORM.imported_at), desc(ScheduleImportBatchORM.id))
            .limit(1)
        )
        return self.session.execute(stmt).scalars().first()

    def get_batch(self, batch_id: int) -> Optional[ScheduleImportBatchORM]:
        stmt = (
            select(ScheduleImportBatchORM)
            .where(ScheduleImportBatchORM.id == batch_id)
            .options(selectinload(ScheduleImportBatchORM.rows))
        )
        return self.session.execute(stmt).scalars().first()

    def list_batches(self, limit: int = 20) -> list[ScheduleImportBatchORM]:
        stmt = (
            select(ScheduleImportBatchORM)
            .order_by(desc(ScheduleImportBatchORM.imported_at), desc(ScheduleImportBatchORM.id))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())


class ScheduleRowRepository:
    def __init__(self, session: Session):
        self.session = session

    def replace_rows(self, batch_id: int, rows: Iterable[TrainRow], imported_at: datetime) -> None:
        for row in rows:
            sort_time = row.arrival or row.departure or imported_at
            entity = ScheduleImportRowORM(
                batch_id=batch_id,
                source_key=row.source_key or f"{row.number}|{row.title}",
                train_uid=row.train_uid,
                transport_type=row.transport_type,
                number=row.number,
                title=row.title,
                arrival=row.arrival,
                departure=row.departure,
                sort_time=sort_time,
            )
            self.session.add(entity)
        self.session.flush()


class RepositoryHub:
    """Единая точка входа в слой репозиториев."""

    def __init__(self, session: Session):
        self.session = session
        self.schedule_imports = ScheduleImportRepository(session)
        self.schedule_rows = ScheduleRowRepository(session)
