from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from config import cfg


@dataclass
class TrainRow:
    """Модель данных для строки таблицы поездов"""
    number: str
    title: str
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None

    def next_time(self, now: datetime) -> Optional[datetime]:
        """Возвращает ближайшее время прибытия/отправления"""
        cands = []
        if self.arrival and self.arrival >= now:
            cands.append(self.arrival)
        if self.departure and self.departure >= now:
            cands.append(self.departure)
        return min(cands) if cands else None

    @staticmethod
    def _fmt_hhmm(dt: Optional[datetime]) -> str:
        """Форматирование времени в ЧЧ:ММ"""
        return dt.astimezone(cfg.tz).strftime("%H:%M") if dt else "—"

    def arrival_str(self) -> str:
        """Строковое представление времени прибытия"""
        return self._fmt_hhmm(self.arrival)

    def departure_str(self) -> str:
        """Строковое представление времени отправления"""
        return self._fmt_hhmm(self.departure)

    def dwell_str(self) -> str:
        """Форматирование времени стоянки"""
        if not self.arrival or not self.departure:
            return "—"
        if self.departure < self.arrival:
            return "—"

        total_min = int((self.departure - self.arrival).total_seconds() // 60)
        h = total_min // 60
        m = total_min % 60

        if h <= 0:
            return f"{m} мин"
        return f"{h} ч {m:02d} мин"