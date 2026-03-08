
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.config import cfg


@dataclass
class TrainRow:
    number: str
    title: str
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None
    source_key: Optional[str] = None
    train_uid: Optional[str] = None
    transport_type: Optional[str] = None

    def next_time(self, now: datetime) -> Optional[datetime]:
        cands = []
        if self.arrival and self.arrival >= now:
            cands.append(self.arrival)
        if self.departure and self.departure >= now:
            cands.append(self.departure)
        return min(cands) if cands else None

    @staticmethod
    def _fmt_hhmm(dt: Optional[datetime]) -> str:
        return dt.astimezone(cfg.tz).strftime("%H:%M") if dt else "—"

    def arrival_str(self) -> str:
        return self._fmt_hhmm(self.arrival)

    def departure_str(self) -> str:
        return self._fmt_hhmm(self.departure)

    def dwell_str(self) -> str:
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

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "arrival": self.arrival.isoformat() if self.arrival else None,
            "departure": self.departure.isoformat() if self.departure else None,
            "arrival_str": self.arrival_str(),
            "departure_str": self.departure_str(),
            "dwell_str": self.dwell_str(),
            "source_key": self.source_key,
            "train_uid": self.train_uid,
            "transport_type": self.transport_type,
        }
