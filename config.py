from __future__ import annotations

import yaml
from typing import Any, Dict
from zoneinfo import ZoneInfo


class Config:
    """Класс для управления конфигурацией приложения"""

    def __init__(self, path: str = "config.yaml"):
        self._config = self._load_config(path)
        self._setup_constants()

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Загрузка конфигурации из YAML файла"""
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _setup_constants(self):
        """Инициализация констант из конфигурации"""
        # Yandex API
        self.yandex_endpoint = "https://api.rasp.yandex-net.ru/v3.0/schedule/"
        self.allowed_transport = {"train", "suburban"}

        # Настройки отображения
        display = self._config["display"]
        self.tz = ZoneInfo(display["timezone"])
        self.past_minutes = int(display["window_past_minutes"])
        self.future_minutes = int(display["window_future_minutes"])
        self.max_rows = int(display["max_rows"])
        self.refresh_seconds = int(display["refresh_seconds"])

        # Сервер
        server = self._config["server"]
        self.host = server["host"]
        self.port = int(server["port"])

        # Yandex API ключи
        yandex = self._config["yandex"]
        self.apikey = yandex["apikey"]
        self.station_code = str(yandex["station_code"])
        self.station_system = str(yandex.get("station_system", "yandex"))
        self.lang = str(yandex.get("lang", "ru_RU"))

        # Безопасность
        security = self._config.get("security", {})
        self.allowed_ips = security.get("allowed_ips", [])
        self.basic_auth_enable = security.get("basic_auth", {}).get("enable", False)
        self.basic_auth_username = security.get("basic_auth", {}).get("username", "")
        self.basic_auth_password = security.get("basic_auth", {}).get("password", "")
        self.token_auth_enable = security.get("token_auth", {}).get("enable", False)
        self.token_auth_tokens = security.get("token_auth", {}).get("tokens", [])

    @property
    def display_timezone(self) -> str:
        """Возвращает временную зону для отображения"""
        return self._config["display"]["timezone"]

    def get(self, key: str, default: Any = None) -> Any:
        """Получение значения из конфигурации"""
        return self._config.get(key, default)


# Глобальный экземпляр конфигурации
cfg = Config()