from __future__ import annotations

from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import cfg
from auth import require_auth, AuthManager
from cache import cache_manager
import re

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'


def detect_device_type():
    """Определение типа устройства по User-Agent"""
    user_agent = request.headers.get('User-Agent', '').lower()

    # Определяем тип устройства
    if re.search(r'mobile|android|iphone|ipod', user_agent):
        return 'mobile'
    elif re.search(r'tablet|ipad', user_agent) and not re.search(r'mobile', user_agent):
        return 'tablet'
    else:
        return 'desktop'


def get_screen_size_class():
    """Определение класса размера экрана на основе куки или заголовков"""
    # Можно добавить определение по куки или другим параметрам
    return 'default'


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

    # Определяем тип устройства
    device_type = detect_device_type()

    # Определяем размер экрана
    screen_size_class = get_screen_size_class()

    # Получаем текущий скин (0=default, 1=compact, 2=ultra_compact, 3=minimalistic)
    skin_index = session.get('skin_index', 0)

    # Конфигурация для каждого скина
    skin_configs = {
        0: {  # default
            'name': 'default',
            'max_rows': cfg.max_rows,
            'screen_padding': "20px 25px",
            'title_class': "",
            'table_class': "",
            'screen_class': ""
        },
        1: {  # compact
            'name': 'compact',
            'max_rows': 12,
            'screen_padding': "15px 20px",
            'title_class': "compact-title",
            'table_class': "compact-table",
            'screen_class': ""
        },
        2: {  # ultra_compact
            'name': 'ultra-compact',
            'max_rows': 20,
            'screen_padding': "10px 15px",
            'title_class': "ultra-compact-title",
            'table_class': "ultra-compact-table",
            'screen_class': ""
        },
        3: {  # minimalistic
            'name': 'minimalistic',
            'max_rows': 15,
            'screen_padding': "18px 20px",
            'title_class': "minimalistic-title",
            'table_class': "minimalistic-table",
            'screen_class': "minimalistic-screen"
        }
    }

    # Получаем конфиг для текущего скина
    config = skin_configs.get(skin_index, skin_configs[0])

    # Корректируем количество строк в зависимости от устройства
    device_row_multipliers = {
        'mobile': 0.6,
        'tablet': 0.8,
        'desktop': 1.0
    }

    multiplier = device_row_multipliers.get(device_type, 1.0)
    adjusted_max_rows = max(4, int(config['max_rows'] * multiplier))

    # Ограничиваем количество строк
    if len(rows) > adjusted_max_rows:
        rows = rows[:adjusted_max_rows]

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
        max_rows_display=adjusted_max_rows,
        screen_padding=config['screen_padding'],
        title_class=config['title_class'],
        table_class=config['table_class'],
        screen_class=config['screen_class'],
        device_type=device_type,
        screen_size_class=screen_size_class,
        skin_name=config['name']
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
    next_index = (current_index + 1) % 4  # Всего 4 скина (0,1,2,3)
    session['skin_index'] = next_index
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(
        host=cfg.host,
        port=cfg.port,
        debug=False
    )