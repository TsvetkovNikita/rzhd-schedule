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

    # Получаем текущий скин (0=default, 1=compact, 2=ultra_compact)
    skin_index = session.get('skin_index', 0)

    # Определяем параметры для каждого скина
    if skin_index == 1:  # compact
        max_rows = 12
        screen_padding = "15px 20px"
        title_class = "compact-title"
        table_class = "compact-table"
    elif skin_index == 2:  # ultra_compact
        max_rows = 20
        screen_padding = "10px 15px"
        title_class = "ultra-compact-title"
        table_class = "ultra-compact-table"
    else:  # default (индекс 0)
        max_rows = cfg.max_rows  # Берем из конфига (8)
        screen_padding = "20px 25px"
        title_class = ""
        table_class = ""

    # Ограничиваем количество строк в соответствии с скином
    if len(rows) > max_rows:
        rows = rows[:max_rows]

    return render_template(
        "index.html",
        rows=rows,
        err=err,
        date_str=now.strftime("%Y-%m-%d"),
        time_str=now.strftime("%H:%M:%S"),
        now_epoch_ms=int(now.timestamp() * 1000),
        tz_name=cfg.display_timezone,
        refresh_seconds=cfg.refresh_seconds,
        simple_auth_enabled=cfg.simple_auth_enable,
        skin_index=skin_index,
        max_rows_display=max_rows,
        screen_padding=screen_padding,
        title_class=title_class,
        table_class=table_class
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


@app.route('/switch_skin')
@require_auth
def switch_skin():
    """Переключение на следующий скин"""
    current_index = session.get('skin_index', 0)
    next_index = (current_index + 1) % 3  # Всего 3 скина (0,1,2)
    session['skin_index'] = next_index
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(
        host=cfg.host,
        port=cfg.port,
        debug=False
    )