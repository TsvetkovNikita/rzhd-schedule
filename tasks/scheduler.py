from __future__ import annotations

import logging
import threading
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

        requested_interval = max(10, cfg.scheduler_interval_seconds)
        effective_interval = cfg.effective_scheduler_interval_seconds()

        if effective_interval > requested_interval:
            self.logger.warning(
                "Scheduler interval increased from %s to %s seconds to stay within Yandex daily limit=%s. "
                "Estimated scheduler requests/day=%s, max requests/cycle=%s",
                requested_interval,
                effective_interval,
                cfg.yandex_daily_request_limit,
                cfg.estimated_scheduler_requests_per_day(),
                cfg.max_yandex_requests_per_cycle(),
            )

        if cfg.scheduler_run_on_startup:
            self.run_import_once("startup")

        self._thread = threading.Thread(target=self._run_loop, name="yandex-import-scheduler", daemon=True)
        self._thread.start()
        self.logger.info(
            "Scheduler started with requested_interval=%s effective_interval=%s seconds",
            requested_interval,
            effective_interval,
        )

    def _run_loop(self) -> None:
        interval = cfg.effective_scheduler_interval_seconds()
        while not self._stop_event.wait(interval):
            self.run_import_once("interval")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


yandex_import_scheduler = YandexImportScheduler()