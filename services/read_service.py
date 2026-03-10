from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.config import cfg
from core.models import TrainRow
from db.database import repository_gateway


class ScheduleReadService:
    """Чтение расписания только из локальной БД."""

    def get_current_rows(self, now: Optional[datetime] = None) -> tuple[
        list[TrainRow], Optional[str], datetime, Optional[dict]]:
        now = now or datetime.now(cfg.tz)

        with repository_gateway.session_scope() as repos:
            batch = repos.schedule_imports.get_latest_success_batch()
            if batch is None:
                interval = cfg.effective_scheduler_interval_seconds()
                return [], (
                    "В базе данных пока нет импортированных расписаний. "
                    f"Автоимпорт выполнится при старте и далее по расписанию (примерно каждые {interval} сек.). "
                ), now, None

            rows = [item.to_train_row() for item in batch.rows]
            meta = {
                "batch_id": batch.id,
                "imported_at": batch.imported_at.isoformat(),
                "row_count": batch.row_count,
                "source": batch.source,
                "window_start": batch.window_start.isoformat(),
                "window_end": batch.window_end.isoformat(),
            }

        rows = [row for row in rows if row.next_time(now) is not None]
        rows.sort(key=lambda row: row.next_time(now) or datetime.max.replace(tzinfo=cfg.tz))
        rows = rows[:cfg.max_rows]

        return rows, None, now, meta

    def get_latest_import_info(self) -> Optional[dict]:
        with repository_gateway.session_scope() as repos:
            batch = repos.schedule_imports.get_latest_success_batch()
            if batch is None:
                return None
            info = {
                "id": batch.id,
                "source": batch.source,
                "station_code": batch.station_code,
                "station_system": batch.station_system,
                "timezone": batch.timezone,
                "status": batch.status,
                "row_count": batch.row_count,
                "imported_at": batch.imported_at.isoformat(),
                "window_start": batch.window_start.isoformat(),
                "window_end": batch.window_end.isoformat(),
                "error_message": batch.error_message,
            }
            return info

    def list_imports(self, limit: int = 20) -> list[dict]:
        with repository_gateway.session_scope() as repos:
            batches = repos.schedule_imports.list_batches(limit=limit)
            result = [
                {
                    "id": batch.id,
                    "source": batch.source,
                    "status": batch.status,
                    "row_count": batch.row_count,
                    "imported_at": batch.imported_at.isoformat(),
                    "window_start": batch.window_start.isoformat(),
                    "window_end": batch.window_end.isoformat(),
                    "error_message": batch.error_message,
                }
                for batch in batches
            ]
            return result


schedule_read_service = ScheduleReadService()
