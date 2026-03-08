from __future__ import annotations

import time
from datetime import datetime
from typing import List, Optional, Tuple

from core.config import cfg
from core.models import TrainRow
from services.read_service import schedule_read_service


class CacheManager:
    """Менеджер кэширования данных, читающий только локальную БД."""

    def __init__(self):
        self._cache = {
            "ts": 0.0,
            "rows": [],
            "err": None,
            "now": None,
            "meta": None,
        }
        self.cache_ttl = 15  # секунд

    def get_rows_cached(self) -> Tuple[List[TrainRow], Optional[str], datetime, Optional[dict]]:
        now = datetime.now(cfg.tz)
        ts = time.time()

        if ts - float(self._cache["ts"]) < self.cache_ttl:
            return (
                self._cache["rows"],
                self._cache["err"],
                self._cache["now"] or now,
                self._cache["meta"],
            )

        rows, err, loaded_now, meta = schedule_read_service.get_current_rows(now)
        self._cache.update({
            "ts": ts,
            "rows": rows,
            "err": err,
            "now": loaded_now,
            "meta": meta,
        })
        return rows, err, loaded_now, meta

    def invalidate(self):
        self._cache["ts"] = 0.0
        self._cache["meta"] = None


cache_manager = CacheManager()
