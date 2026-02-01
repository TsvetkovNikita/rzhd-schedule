from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import yaml
import requests
from flask import Flask, Response, render_template_string


# -------------------- Config --------------------

def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG = load_config()

YANDEX_ENDPOINT = "https://api.rasp.yandex-net.ru/v3.0/schedule/"
ALLOWED_TRANSPORT = {"train", "suburban"}

TZ = ZoneInfo(CFG["display"]["timezone"])
PAST = int(CFG["display"]["window_past_minutes"])
FUTURE = int(CFG["display"]["window_future_minutes"])
MAX_ROWS = int(CFG["display"]["max_rows"])
REFRESH_SECONDS = int(CFG["display"]["refresh_seconds"])

HOST = CFG["server"]["host"]
PORT = int(CFG["server"]["port"])

APIKEY = CFG["yandex"]["apikey"]
STATION_CODE = str(CFG["yandex"]["station_code"])
STATION_SYSTEM = str(CFG["yandex"].get("station_system", "yandex"))
LANG = str(CFG["yandex"].get("lang", "ru_RU"))


# -------------------- Data model --------------------

@dataclass
class TrainRow:
    number: str
    title: str
    arrival: Optional[datetime] = None
    departure: Optional[datetime] = None

    def next_time(self, now: datetime) -> Optional[datetime]:
        cands = []
        if self.arrival and self.arrival >= now:
            cands.append(self.arrival)
        if self.departure and self.departure >= now:
            cands.append(self.departure)
        return min(cands) if cands else None

    @staticmethod
    def _fmt_hhmm(dt: Optional[datetime]) -> str:
        return dt.astimezone(TZ).strftime("%H:%M") if dt else "—"

    def arrival_str(self) -> str:
        return self._fmt_hhmm(self.arrival)

    def departure_str(self) -> str:
        return self._fmt_hhmm(self.departure)

    def dwell_str(self) -> str:
        """
        Время стоянки = departure - arrival.
        Формат: "12 мин" или "1 ч 05 мин". Если нет пары времен — "—".
        """
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


# -------------------- Yandex API fetch --------------------

def _get_json(params: Dict[str, str], timeout: int = 10) -> Dict[str, Any]:
    r = requests.get(YANDEX_ENDPOINT, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str)


def fetch_items_for_date(date_str: str, event: str) -> List[Tuple[str, str, str, datetime]]:
    """
    Returns list of (key, number, title, event_dt)
    key prefers thread.uid; fallback number|title
    """
    params = {
        "apikey": APIKEY,
        "station": STATION_CODE,
        "lang": LANG,
        "format": "json",
        "date": date_str,  # YYYY-MM-DD
        "event": event,  # departure | arrival
        "system": STATION_SYSTEM,  # yandex | express | esr
        "result_timezone": CFG["display"]["timezone"],
    }
    data = _get_json(params)

    out: List[Tuple[str, str, str, datetime]] = []
    for item in data.get("schedule", []):
        thread = item.get("thread") or {}
        transport = (thread.get("transport_type") or "").strip()
        if transport not in ALLOWED_TRANSPORT:
            continue

        dt_raw = item.get("arrival" if event == "arrival" else "departure")
        dt = _parse_iso(dt_raw)
        if not dt:
            continue
        dt = dt.astimezone(TZ)

        number = (str(thread.get("number") or "").strip() or "—")
        title = (str(thread.get("title") or thread.get("short_title") or "").strip() or "—")

        uid = str(thread.get("uid") or "").strip()
        key = uid if uid else f"{number}|{title}"

        out.append((key, number, title, dt))

    return out


def collect_window_rows(now: datetime) -> List[TrainRow]:
    start = now - timedelta(minutes=PAST)
    end = now + timedelta(minutes=FUTURE)

    dates = {now.date().isoformat(), (now.date() + timedelta(days=1)).isoformat()}
    groups: Dict[str, TrainRow] = {}

    for d in sorted(dates):
        # arrivals
        try:
            for key, number, title, dt in fetch_items_for_date(d, "arrival"):
                if not (start <= dt <= end):
                    continue
                row = groups.setdefault(key, TrainRow(number=number, title=title))
                row.arrival = dt if row.arrival is None else min(row.arrival, dt)
        except Exception:
            pass

        # departures
        try:
            for key, number, title, dt in fetch_items_for_date(d, "departure"):
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

    rows.sort(key=lambda r: r.next_time(now) or datetime.max.replace(tzinfo=TZ))
    return rows[:MAX_ROWS]


# -------------------- Simple cache --------------------

_CACHE: Dict[str, Any] = {"ts": 0.0, "rows": [], "err": None, "now": None}


def get_rows_cached() -> Tuple[List[TrainRow], Optional[str], datetime]:
    now = datetime.now(TZ)
    ts = time.time()
    if ts - float(_CACHE["ts"]) < 15:
        return _CACHE["rows"], _CACHE["err"], _CACHE["now"] or now

    try:
        rows = collect_window_rows(now)
        err = None
    except Exception as e:
        rows = []
        err = f"{type(e).__name__}: {e}"

    _CACHE.update({"ts": ts, "rows": rows, "err": err, "now": now})
    return rows, err, now


# -------------------- Web UI --------------------

HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <meta http-equiv="refresh" content="{{ refresh_seconds }}">
  <title>Табло — Саратов-1</title>
  <style>
    :root{
      --bg:#0b0f14;
      --text:#e6edf3;
      --muted:rgba(230,237,243,.70);
      --border:rgba(255,255,255,.10);
      --panel:rgba(255,255,255,.04);
      --head:rgba(255,255,255,.07);

      --arr:rgba(40, 200, 120, 1);
      --dep:rgba(255, 90, 90, 1);
    }

    html, body { height: 100%; }
    body { margin:0; background:var(--bg); color:var(--text); font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; overflow:hidden; }

    .screen { height: 100vh; display:flex; flex-direction:column; padding: 22px 26px; box-sizing:border-box; gap: 14px; }

    .top { display:flex; align-items:flex-end; justify-content:space-between; gap: 16px; }
    .title-block { display:flex; flex-direction:column; gap: 6px; }
    .h1 { font-size: clamp(34px, 3.2vw, 72px); font-weight: 900; letter-spacing: .2px; line-height: 1.05; }
    .sub { font-size: clamp(14px, 1.15vw, 18px); color: var(--muted); font-weight: 800; }

    .clock {
      text-align:right;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--panel);
      min-width: 220px;
    }
    .clock .date { font-size: clamp(16px, 1.2vw, 22px); color: var(--dep); font-weight: 800; }
    .clock .time { font-size: clamp(30px, 2.7vw, 60px); color: var(--dep); font-weight: 950; font-variant-numeric: tabular-nums; line-height: 1.05; }

    .table-title {
      padding: 12px 16px;
      border-radius: 16px;
      background: var(--panel);
      border: 1px solid var(--border);
      font-size: clamp(18px, 1.35vw, 26px);
      font-weight: 900;
      letter-spacing: .2px;
      display:flex;
      justify-content:space-between;
      align-items:center;
      gap: 10px;
    }
    .table-title .hint { color: var(--muted); font-weight: 800; font-size: clamp(14px, 1.1vw, 18px); }

    .box {
      flex: 1;
      min-height: 0;
      border-radius: 18px;
      overflow:hidden;
      border:1px solid var(--border);
      background: rgba(255,255,255,.02);
      display:flex;
    }

    table { width:100%; border-collapse:collapse; table-layout:fixed; }
    thead th {
      background: var(--head);
      padding: 16px 14px;
      font-size: clamp(16px, 1.2vw, 22px);
      text-align:center;
      border-bottom: 1px solid var(--border);
    }
    tbody td {
      padding: 18px 14px;
      font-size: clamp(22px, 1.9vw, 44px);
      text-align:center;
      border-top: 1px solid rgba(255,255,255,.08);
      vertical-align:middle;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* widths */
    .c-num { width: 16%; }
    .c-route { width: 44%; }
    .c-arr { width: 13%; }
    .c-dwell { width: 14%; }
    .c-dep { width: 13%; }

    .arr { color: var(--arr); font-weight: 950; }
    .dep { color: var(--dep); font-weight: 950; }
    .dwell { color: rgba(230,237,243,.92); font-weight: 900; }
    .empty { color: rgba(230,237,243,.35); font-weight: 800; }

    .err { margin-top: 6px; font-size: clamp(14px, 1.05vw, 18px); color: #ffb4b4; }
  </style>
</head>
<body>
  <div class="screen">
    <div class="top">
      <div class="title-block">
        <div class="h1">Онлайн-табло: Саратов-1</div>
        <div class="sub">Саратовское время</div>
      </div>

      <div class="clock">
        <div class="date">{{ date_str }}</div>
        <div class="time">{{ time_str }}</div>
      </div>
    </div>

    <div class="table-title">
      <div>Ближайшие поезда / Upcoming trains</div>
      <div class="hint">До +12 часов · максимум {{ max_rows }}</div>
    </div>

    <div class="box">
      <table>
        <thead>
          <tr>
            <th class="c-num">№ / Train</th>
            <th class="c-route">Маршрут / Route</th>
            <th class="c-arr">Приб / Arrival</th>
            <th class="c-dwell">Стоянка / Dwell</th>
            <th class="c-dep">Отпр / Departure</th>
          </tr>
        </thead>
        <tbody>
          {% if rows %}
            {% for r in rows %}
              {% set a = r.arrival_str() %}
              {% set d = r.departure_str() %}
              {% set w = r.dwell_str() %}
              <tr>
                <td class="c-num"><b>{{ r.number }}</b></td>
                <td class="c-route">{{ r.title }}</td>
                <td class="c-arr {{ 'arr' if a != '—' else 'empty' }}">{{ a }}</td>
                <td class="c-dwell {{ 'dwell' if w != '—' else 'empty' }}">{{ w }}</td>
                <td class="c-dep {{ 'dep' if d != '—' else 'empty' }}">{{ d }}</td>
              </tr>
            {% endfor %}
          {% else %}
            <tr><td colspan="5" style="padding:22px; font-size:24px; color:rgba(230,237,243,.75);">Нет поездов в заданном окне</td></tr>
          {% endif %}
        </tbody>
      </table>
    </div>

    {% if err %}
      <div class="err">Ошибка обновления данных: {{ err }}</div>
    {% endif %}
  </div>

  <script>
    (() => {
      const tz = "{{ tz_name }}";
      let ms = {{ now_epoch_ms }};

      const dateEl = document.querySelector(".clock .date");
      const timeEl = document.querySelector(".clock .time");

      // en-CA удобно тем, что дает YYYY-MM-DD
      const fmtDate = new Intl.DateTimeFormat("en-CA", {
        timeZone: tz,
        year: "numeric",
        month: "2-digit",
        day: "2-digit"
      });

      const fmtTime = new Intl.DateTimeFormat("ru-RU", {
        timeZone: tz,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      });

      function render() {
        const d = new Date(ms);
        dateEl.textContent = fmtDate.format(d);
        timeEl.textContent = fmtTime.format(d);
      }

      render();
      setInterval(() => {
        ms += 1000;
        render();
      }, 1000);
    })();
  </script>
</body>
</html>
"""

app = Flask(__name__)


@app.get("/")
def index() -> str:
    rows, err, now = get_rows_cached()

    return render_template_string(
        HTML,
        rows=rows,
        err=err,
        date_str=now.strftime("%Y-%m-%d"),
        time_str=now.strftime("%H:%M:%S"),
        now_epoch_ms=int(now.timestamp() * 1000),
        tz_name=CFG["display"]["timezone"],
        max_rows=MAX_ROWS,
        refresh_seconds=REFRESH_SECONDS,
    )


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
