from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from api_client import yandex_client
from config import cfg
from database import repository_gateway
from models import TrainRow


@dataclass
class ImportResult:
    batch_id: int
    imported_at: datetime
    row_count: int
    status: str
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "imported_at": self.imported_at.isoformat(),
            "row_count": self.row_count,
            "status": self.status,
            "error_message": self.error_message,
        }


class ScheduleImportService:
    """Импорт расписания из внешних источников в локальную БД."""

    def import_from_yandex(self, now: Optional[datetime] = None) -> ImportResult:
        now = now or datetime.now(cfg.tz)
        window_start = now - timedelta(minutes=cfg.past_minutes)
        window_end = now + timedelta(minutes=cfg.future_minutes)
        request_payload = {
            "source": "yandex",
            "station_code": cfg.station_code,
            "station_system": cfg.station_system,
            "timezone": cfg.display_timezone,
            "lang": cfg.lang,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "events": ["arrival", "departure"],
            "dates": sorted({now.date().isoformat(), (now.date() + timedelta(days=1)).isoformat()}),
        }

        try:
            rows = yandex_client.collect_window_rows(now)
        except Exception as exc:
            with repository_gateway.session_scope() as repos:
                batch = repos.schedule_imports.create_batch(
                    source="yandex",
                    station_code=cfg.station_code,
                    station_system=cfg.station_system,
                    timezone=cfg.display_timezone,
                    window_start=window_start,
                    window_end=window_end,
                    imported_at=now,
                    status="failed",
                    row_count=0,
                    request_payload=request_payload,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            raise RuntimeError(f"Не удалось импортировать данные из Яндекс.Расписаний: {exc}") from exc

        with repository_gateway.session_scope() as repos:
            batch = repos.schedule_imports.create_batch(
                source="yandex",
                station_code=cfg.station_code,
                station_system=cfg.station_system,
                timezone=cfg.display_timezone,
                window_start=window_start,
                window_end=window_end,
                imported_at=now,
                status="success",
                row_count=len(rows),
                request_payload=request_payload,
                error_message=None,
            )
            repos.schedule_rows.replace_rows(batch.id, rows, now)

        return ImportResult(
            batch_id=batch.id,
            imported_at=now,
            row_count=len(rows),
            status="success",
        )


class ScheduleReadService:
    """Чтение расписания только из локальной БД."""

    def get_current_rows(self, now: Optional[datetime] = None) -> tuple[list[TrainRow], Optional[str], datetime, Optional[dict]]:
        now = now or datetime.now(cfg.tz)

        with repository_gateway.session_scope() as repos:
            batch = repos.schedule_imports.get_latest_success_batch()
            if batch is None:
                return [], "В базе данных пока нет импортированных расписаний. Выполните POST /api/v1/imports/yandex или GET /refresh.", now, None
            rows = [item.to_train_row() for item in batch.rows]

        rows = [row for row in rows if row.next_time(now) is not None]
        rows.sort(key=lambda row: row.next_time(now) or datetime.max.replace(tzinfo=cfg.tz))
        rows = rows[:cfg.max_rows]

        meta = {
            "batch_id": batch.id,
            "imported_at": batch.imported_at.isoformat(),
            "row_count": batch.row_count,
            "source": batch.source,
            "window_start": batch.window_start.isoformat(),
            "window_end": batch.window_end.isoformat(),
        }
        return rows, None, now, meta

    def get_latest_import_info(self) -> Optional[dict]:
        with repository_gateway.session_scope() as repos:
            batch = repos.schedule_imports.get_latest_success_batch()
            if batch is None:
                return None
            return {
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

    def list_imports(self, limit: int = 20) -> list[dict]:
        with repository_gateway.session_scope() as repos:
            batches = repos.schedule_imports.list_batches(limit=limit)
            return [
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


schedule_import_service = ScheduleImportService()
schedule_read_service = ScheduleReadService()
