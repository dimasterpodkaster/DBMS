"""Настройки приложения, задаваемые переменными окружения"""

import os


def _as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_config():
    return {
        "REDIS_SENTINELS": os.getenv(
            "REDIS_SENTINELS",
            "sentinel-1:26379,sentinel-2:26379,sentinel-3:26379",
        ),
        "REDIS_MASTER_NAME": os.getenv("REDIS_MASTER_NAME", "mymaster"),
        "REDIS_SOCKET_TIMEOUT": float(
            os.getenv("REDIS_SOCKET_TIMEOUT", "2.0")
        ),
        "REDIS_SOCKET_CONNECT_TIMEOUT": float(
            os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "2.0")
        ),
        "REDIS_RETRY_COUNT": int(os.getenv("REDIS_RETRY_COUNT", "3")),
        "REDIS_READ_FROM_REPLICAS": _as_bool(
            os.getenv("REDIS_READ_FROM_REPLICAS", "true")
        ),
        "CHECK_REDIS_ON_START": _as_bool(
            os.getenv("CHECK_REDIS_ON_START", "true")
        ),
    }
