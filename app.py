from __future__ import annotations

from flask import Flask, render_template
from config import cfg
from auth import require_auth
from cache import cache_manager

app = Flask(__name__)


@app.before_request
def before_request():
    """Логирование запросов"""
    from auth import AuthManager
    client_ip = AuthManager.get_client_ip()
    app.logger.info(f"Request from {client_ip} to {request.path}")


@app.get("/")
@require_auth
def index() -> str:
    """Главная страница с табло"""
    rows, err, now = cache_manager.get_rows_cached()

    return render_template(
        "index.html",
        rows=rows,
        err=err,
        date_str=now.strftime("%Y-%m-%d"),
        time_str=now.strftime("%H:%M:%S"),
        now_epoch_ms=int(now.timestamp() * 1000),
        tz_name=cfg.display_timezone,
        max_rows=cfg.max_rows,
        refresh_seconds=cfg.refresh_seconds,
    )


@app.get("/health")
def health():
    """Эндпоинт для проверки работоспособности"""
    return {"status": "ok", "service": "railway-board"}


@app.get("/refresh")
@require_auth
def refresh_cache():
    """Принудительное обновление кэша"""
    cache_manager.invalidate()
    return {"status": "cache invalidated"}


if __name__ == "__main__":
    app.run(
        host=cfg.host,
        port=cfg.port,
        debug=False
    )