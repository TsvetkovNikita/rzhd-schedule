
from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import yaml


class Config:
    """Управление конфигурацией приложения."""

    def __init__(self, path: str = "config.yaml"):
        self.path = path
        self._config = self._load_config(path)
        self._setup_constants()

    def _load_config(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _setup_constants(self) -> None:
        app_cfg = self._config.get("app", {})
        self.secret_key = str(app_cfg.get("secret_key", "change-me-secret-key"))

        self.yandex_endpoint = "https://api.rasp.yandex.net/v3.0/schedule/"
        self.allowed_transport = {"train", "suburban"}

        display = self._config["display"]
        self.tz = ZoneInfo(display["timezone"])
        self.past_minutes = int(display["window_past_minutes"])
        self.future_minutes = int(display["window_future_minutes"])
        self.max_rows = int(display["max_rows"])
        self.refresh_seconds = int(display["refresh_seconds"])
        self.skin = str(display.get("skin", "classic"))
        self.available_skins = tuple(str(item) for item in display.get(
            "available_skins",
            ["classic", "full_hd", "half_hd", "contrast"],
        ))

        server = self._config["server"]
        self.host = server["host"]
        self.port = int(server["port"])

        yandex = self._config["yandex"]
        self.apikey = yandex["apikey"]
        self.station_code = str(yandex["station_code"])
        self.station_system = str(yandex.get("station_system", "yandex"))
        self.lang = str(yandex.get("lang", "ru_RU"))

        database = self._config.get("database", {})
        self.db_host = str(database.get("host", "127.0.0.1"))
        self.db_port = int(database.get("port", 5432))
        self.db_name = str(database.get("name", "rzhd_schedule"))
        self.db_user = str(database.get("user", "postgres"))
        self.db_password = str(database.get("password", "postgres"))
        self.db_echo = bool(database.get("echo", False))
        self.db_auto_create = bool(database.get("auto_create", False))
        self.db_pool_pre_ping = bool(database.get("pool_pre_ping", True))

        scheduler = self._config.get("scheduler", {})
        self.scheduler_enabled = bool(scheduler.get("enabled", True))
        self.scheduler_interval_seconds = int(scheduler.get("interval_seconds", 180))
        self.scheduler_run_on_startup = bool(scheduler.get("run_on_startup", True))

        security = self._config.get("security", {})
        self.allowed_ips = security.get("allowed_ips", [])
        self.basic_auth_enable = security.get("basic_auth", {}).get("enable", False)
        self.basic_auth_username = security.get("basic_auth", {}).get("username", "")
        self.basic_auth_password = security.get("basic_auth", {}).get("password", "")
        self.token_auth_enable = security.get("token_auth", {}).get("enable", False)
        self.token_auth_tokens = security.get("token_auth", {}).get("tokens", [])

        simple_auth = security.get("simple_auth", {})
        self.simple_auth_enable = simple_auth.get("enable", False)
        self.simple_auth_password = simple_auth.get("password", "")

    @property
    def display_timezone(self) -> str:
        return self._config["display"]["timezone"]

    @property
    def database_url(self) -> str:
        explicit_url = os.getenv("DATABASE_URL")
        if explicit_url:
            return explicit_url
        password = quote_plus(self.db_password)
        return f"postgresql+psycopg2://{self.db_user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"

    def resolve_skin(self, requested_skin: str | None = None) -> str:
        candidate = (requested_skin or self.skin or "classic").strip().lower()
        allowed = set(self.available_skins)
        return candidate if candidate in allowed else "classic"

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)


cfg = Config()
