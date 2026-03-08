
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from clients.yandex_client import yandex_client
from core.config import cfg
from db.database import repository_gateway


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
            batch_id = batch.id
            repos.schedule_rows.replace_rows(batch_id, rows, now)

        return ImportResult(
            batch_id=batch_id,
            imported_at=now,
            row_count=len(rows),
            status="success",
        )


schedule_import_service = ScheduleImportService()
