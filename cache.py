from __future__ import annotations

import time
from datetime import datetime
from typing import List, Optional, Tuple
from config import cfg
from models import TrainRow
from api_client import yandex_client


class CacheManager:
    """Менеджер кэширования данных"""

    def __init__(self):
        self._cache = {
            "ts": 0.0,
            "rows": [],
            "err": None,
            "now": None
        }
        self.cache_ttl = 15  # секунд

    def get_rows_cached(self) -> Tuple[List[TrainRow], Optional[str], datetime]:
        """Получение данных с кэшированием"""
        now = datetime.now(cfg.tz)
        ts = time.time()

        if ts - float(self._cache["ts"]) < self.cache_ttl:
            return self._cache["rows"], self._cache["err"], self._cache["now"] or now

        try:
            rows = yandex_client.collect_window_rows(now)
            err = None
        except Exception as e:
            rows = []
            err = f"{type(e).__name__}: {e}"

        self._cache.update({
            "ts": ts,
            "rows": rows,
            "err": err,
            "now": now
        })

        return rows, err, now

    def invalidate(self):
        """Сброс кэша"""
        self._cache["ts"] = 0.0


# Глобальный экземпляр кэша
cache_manager = CacheManager()