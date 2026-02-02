from __future__ import annotations

from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import cfg
from auth import require_auth, AuthManager
from cache import cache_manager

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Для сессий


@app.before_request
def before_request():
    """Логирование запросов"""
    client_ip = AuthManager.get_client_ip()
    app.logger.info(f"Request from {client_ip} to {request.path}")


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа с простой авторизацией"""
    if not cfg.simple_auth_enable:
        return redirect(url_for('index'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        if AuthManager.check_simple_auth(password):
            session['authenticated'] = True
            return redirect(url_for('index'))
        else:
            flash('Неверный пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Выход из системы"""
    session.pop('authenticated', None)
    return redirect(url_for('login'))


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
        simple_auth_enabled=cfg.simple_auth_enable,
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