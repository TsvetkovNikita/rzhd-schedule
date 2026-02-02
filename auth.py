from __future__ import annotations

import ipaddress
from functools import wraps
from typing import Callable, List
from flask import request, Response, abort, session, redirect, url_for
from config import cfg


class AuthManager:
    """Менеджер аутентификации и авторизации"""

    @staticmethod
    def get_client_ip() -> str:
        """Получение реального IP клиента с учетом прокси"""
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr

    @staticmethod
    def check_ip_allowed(client_ip: str) -> bool:
        """Проверка разрешенного IP-адреса"""
        if not cfg.allowed_ips:  # Если список пустой - доступ всем
            return True

        try:
            ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            return False

        for allowed in cfg.allowed_ips:
            try:
                network = ipaddress.ip_network(allowed, strict=False)
                if ip_obj in network:
                    return True
            except ValueError:
                # Если это не сеть, а конкретный IP
                if client_ip == allowed:
                    return True
        return False

    @staticmethod
    def check_basic_auth(username: str, password: str) -> bool:
        """Проверка базовой HTTP-авторизации"""
        if not cfg.basic_auth_enable:
            return True
        return (username == cfg.basic_auth_username and
                password == cfg.basic_auth_password)

    @staticmethod
    def check_token_auth(token: str) -> bool:
        """Проверка токен-авторизации"""
        if not cfg.token_auth_enable:
            return True
        return token in cfg.token_auth_tokens

    @staticmethod
    def check_simple_auth(password: str) -> bool:
        """Проверка простой авторизации по паролю"""
        if not cfg.simple_auth_enable:
            return True
        return password == cfg.simple_auth_password


def require_auth(f: Callable):
    """Декоратор для защиты маршрутов"""

    @wraps(f)
    def decorated(*args, **kwargs):
        # Для простой авторизации проверяем сессию
        if cfg.simple_auth_enable:
            if session.get('authenticated'):
                return f(*args, **kwargs)
            else:
                return redirect(url_for('login'))

        auth_manager = AuthManager()
        client_ip = auth_manager.get_client_ip()

        # Проверка IP (если простая авторизация отключена)
        if not auth_manager.check_ip_allowed(client_ip):
            abort(403, description="IP address not allowed")

        # Проверка базовой авторизации
        if cfg.basic_auth_enable:
            auth = request.authorization
            if not auth or not auth_manager.check_basic_auth(auth.username, auth.password):
                return Response(
                    'Please login with proper credentials',
                    401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'}
                )

        # Проверка токена (если передан в заголовке)
        if cfg.token_auth_enable and request.headers.get('X-API-Token'):
            token = request.headers.get('X-API-Token')
            if not auth_manager.check_token_auth(token):
                abort(401, description="Invalid token")

        return f(*args, **kwargs)

    return decorated