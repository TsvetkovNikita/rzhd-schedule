
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from core.config import cfg
from services.cache_service import cache_manager
from services.import_service import schedule_import_service


class YandexImportScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False
        self.logger = logging.getLogger("rzhd.scheduler")

    def run_import_once(self, reason: str) -> None:
        try:
            result = schedule_import_service.import_from_yandex()
            cache_manager.invalidate()
            self.logger.info(
                "Yandex import completed: reason=%s batch_id=%s row_count=%s imported_at=%s",
                reason,
                result.batch_id,
                result.row_count,
                result.imported_at.isoformat(),
            )
        except Exception:
            self.logger.exception("Yandex import failed: reason=%s", reason)

    def start(self) -> None:
        if not cfg.scheduler_enabled:
            self.logger.info("Scheduler disabled in config")
            return
        if self._started:
            return
        self._started = True

        if cfg.scheduler_run_on_startup:
            self.run_import_once("startup")

        self._thread = threading.Thread(target=self._run_loop, name="yandex-import-scheduler", daemon=True)
        self._thread.start()
        self.logger.info("Scheduler started with interval=%s seconds", cfg.scheduler_interval_seconds)

    def _run_loop(self) -> None:
        interval = max(10, cfg.scheduler_interval_seconds)
        while not self._stop_event.wait(interval):
            self.run_import_once("interval")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


yandex_import_scheduler = YandexImportScheduler()
