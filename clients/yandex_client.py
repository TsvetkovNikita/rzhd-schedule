from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from core.config import cfg
from core.models import TrainRow


@dataclass
class YandexFetchItem:
    source_key: str
    number: str
    title: str
    event_time: datetime
    event_type: str
    train_uid: Optional[str] = None
    transport_type: Optional[str] = None


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

    def fetch_items_for_date(self, date_str: str, event: str) -> List[YandexFetchItem]:
        """Получение расписания на определенную дату"""
        params = {
            "apikey": cfg.apikey,
            "station": cfg.station_code,
            "lang": cfg.lang,
            "format": "json",
            "date": date_str,
            "event": event,
            "system": cfg.station_system,
            "result_timezone": cfg.display_timezone,
        }

        data = self._get_json(params)
        out: List[YandexFetchItem] = []

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

            uid = str(thread.get("uid") or "").strip() or None
            key = uid if uid else f"{number}|{title}"

            out.append(
                YandexFetchItem(
                    source_key=key,
                    number=number,
                    title=title,
                    event_time=dt,
                    event_type=event,
                    train_uid=uid,
                    transport_type=transport,
                )
            )

        return out

    def collect_window_rows(self, now: datetime) -> List[TrainRow]:
        """Сбор данных за временное окно"""
        start = now - timedelta(minutes=cfg.past_minutes)
        end = now + timedelta(minutes=cfg.future_minutes)

        dates = {now.date().isoformat(), (now.date() + timedelta(days=1)).isoformat()}
        groups: Dict[str, TrainRow] = {}

        for d in sorted(dates):
            for event in ("arrival", "departure"):
                for item in self.fetch_items_for_date(d, event):
                    if not (start <= item.event_time <= end):
                        continue

                    row = groups.setdefault(
                        item.source_key,
                        TrainRow(
                            number=item.number,
                            title=item.title,
                            source_key=item.source_key,
                            train_uid=item.train_uid,
                            transport_type=item.transport_type,
                        ),
                    )
                    if item.event_type == "arrival":
                        row.arrival = item.event_time if row.arrival is None else min(row.arrival, item.event_time)
                    else:
                        row.departure = item.event_time if row.departure is None else min(row.departure, item.event_time)

        rows: List[TrainRow] = []
        for r in groups.values():
            if r.next_time(now) is None:
                continue
            rows.append(r)

        rows.sort(key=lambda r: r.next_time(now) or datetime.max.replace(tzinfo=cfg.tz))
        return rows[:cfg.max_rows]


# Глобальный экземпляр клиента

yandex_client = YandexAPIClient()
