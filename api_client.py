from __future__ import annotations

import requests
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from config import cfg
from models import TrainRow


class YandexAPIClient:
    """Клиент для работы с API Яндекс.Расписаний"""

    @staticmethod
    def _get_json(params: Dict[str, str], timeout: int = 10) -> Dict[str, Any]:
        """Выполнение GET запроса к API"""
        r = requests.get(cfg.yandex_endpoint, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
        """Парсинг ISO строки даты-времени"""
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str)

    def fetch_items_for_date(self, date_str: str, event: str) -> List[Tuple[str, str, str, datetime]]:
        """
        Получение расписания на определенную дату

        Returns:
            Список кортежей (key, number, title, event_dt)
        """
        params = {
            "apikey": cfg.apikey,
            "station": cfg.station_code,
            "lang": cfg.lang,
            "format": "json",
            "date": date_str,  # YYYY-MM-DD
            "event": event,  # departure | arrival
            "system": cfg.station_system,
            "result_timezone": cfg.display_timezone,
        }

        data = self._get_json(params)
        out: List[Tuple[str, str, str, datetime]] = []

        for item in data.get("schedule", []):
            thread = item.get("thread") or {}
            transport = (thread.get("transport_type") or "").strip()

            if transport not in cfg.allowed_transport:
                continue

            dt_raw = item.get("arrival" if event == "arrival" else "departure")
            dt = self._parse_iso(dt_raw)
            if not dt:
                continue
            dt = dt.astimezone(cfg.tz)

            number = (str(thread.get("number") or "").strip() or "—")
            title = (str(thread.get("title") or thread.get("short_title") or "").strip() or "—")

            uid = str(thread.get("uid") or "").strip()
            key = uid if uid else f"{number}|{title}"

            out.append((key, number, title, dt))

        return out

    def collect_window_rows(self, now: datetime) -> List[TrainRow]:
        """Сбор данных за временное окно"""
        start = now - timedelta(minutes=cfg.past_minutes)
        end = now + timedelta(minutes=cfg.future_minutes)

        dates = {now.date().isoformat(), (now.date() + timedelta(days=1)).isoformat()}
        groups: Dict[str, TrainRow] = {}

        for d in sorted(dates):
            # Прибытия
            try:
                for key, number, title, dt in self.fetch_items_for_date(d, "arrival"):
                    if not (start <= dt <= end):
                        continue
                    row = groups.setdefault(key, TrainRow(number=number, title=title))
                    row.arrival = dt if row.arrival is None else min(row.arrival, dt)
            except Exception:
                pass

            # Отправления
            try:
                for key, number, title, dt in self.fetch_items_for_date(d, "departure"):
                    if not (start <= dt <= end):
                        continue
                    row = groups.setdefault(key, TrainRow(number=number, title=title))
                    row.departure = dt if row.departure is None else min(row.departure, dt)
            except Exception:
                pass

        rows: List[TrainRow] = []
        for r in groups.values():
            if r.next_time(now) is None:
                continue
            rows.append(r)

        rows.sort(key=lambda r: r.next_time(now) or datetime.max.replace(tzinfo=cfg.tz))
        return rows[:cfg.max_rows]


# Глобальный экземпляр клиента
yandex_client = YandexAPIClient()