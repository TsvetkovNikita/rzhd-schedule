
from __future__ import annotations

import os

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from core.config import cfg
from db.database import init_database, repository_gateway
from services.cache_service import cache_manager
from services.import_service import schedule_import_service
from services.read_service import schedule_read_service
from tasks.scheduler import yandex_import_scheduler
from web.auth import AuthManager, require_auth


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = cfg.secret_key

    init_database()

    @app.before_request
    def before_request():
        client_ip = AuthManager.get_client_ip()
        app.logger.info("Request from %s to %s", client_ip, request.path)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if not cfg.simple_auth_enable:
            return redirect(url_for('index'))

        if request.method == 'POST':
            password = request.form.get('password', '')
            if AuthManager.check_simple_auth(password):
                session['authenticated'] = True
                return redirect(url_for('index'))
            flash('Неверный пароль', 'error')

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.pop('authenticated', None)
        return redirect(url_for('login'))

    @app.get('/')
    @require_auth
    def index() -> str:
        rows, err, now, meta = cache_manager.get_rows_cached()
        requested_skin = request.args.get('skin')
        skin = cfg.resolve_skin(requested_skin)
        return render_template(
            'index.html',
            rows=rows,
            err=err,
            date_str=now.strftime('%Y-%m-%d'),
            time_str=now.strftime('%H:%M:%S'),
            now_epoch_ms=int(now.timestamp() * 1000),
            tz_name=cfg.display_timezone,
            max_rows=cfg.max_rows,
            refresh_seconds=cfg.refresh_seconds,
            simple_auth_enabled=cfg.simple_auth_enable,
            latest_import=meta,
            current_skin=skin,
            available_skins=cfg.available_skins,
        )

    @app.get('/health')
    def health():
        try:
            db_ok = repository_gateway.ping()
        except Exception as exc:
            return jsonify({
                'status': 'degraded',
                'service': 'railway-board',
                'database': 'error',
                'error': f'{type(exc).__name__}: {exc}',
            }), 500

        return jsonify({
            'status': 'ok',
            'service': 'railway-board',
            'database': 'ok' if db_ok else 'unknown',
            'scheduler_enabled': cfg.scheduler_enabled,
            'scheduler_interval_seconds': cfg.scheduler_interval_seconds,
        })

    @app.get('/refresh')
    @require_auth
    def refresh_cache():
        result = schedule_import_service.import_from_yandex()
        cache_manager.invalidate()
        return jsonify({'status': 'ok', 'import': result.to_dict()})

    @app.get('/api/v1/trains')
    @require_auth
    def api_get_trains():
        rows, err, now, meta = cache_manager.get_rows_cached()
        return jsonify({
            'status': 'ok' if not err else 'empty',
            'source': 'database',
            'current_time': now.isoformat(),
            'latest_import': meta,
            'rows': [row.to_dict() for row in rows],
            'error': err,
        })

    @app.post('/api/v1/imports/yandex')
    @require_auth
    def api_import_yandex():
        result = schedule_import_service.import_from_yandex()
        cache_manager.invalidate()
        return jsonify({
            'status': 'ok',
            'message': 'Импорт из Яндекс.Расписаний сохранён в локальную БД',
            'import': result.to_dict(),
        }), 201

    @app.get('/api/v1/imports/latest')
    @require_auth
    def api_latest_import():
        latest = schedule_read_service.get_latest_import_info()
        if latest is None:
            return jsonify({
                'status': 'empty',
                'message': 'Импортов пока нет',
                'import': None,
            }), 404
        return jsonify({'status': 'ok', 'import': latest})

    @app.get('/api/v1/imports')
    @require_auth
    def api_list_imports():
        try:
            limit = int(request.args.get('limit', 20))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 100))
        return jsonify({'status': 'ok', 'imports': schedule_read_service.list_imports(limit=limit)})

    should_start_scheduler = os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug
    if should_start_scheduler:
        yandex_import_scheduler.start()

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host=cfg.host, port=cfg.port, debug=False)
