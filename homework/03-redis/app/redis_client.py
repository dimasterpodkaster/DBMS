"""Подключения к Redis через Sentinel и резервный маршрут чтения"""

from redis.backoff import ExponentialBackoff
from redis.exceptions import RedisError
from redis.retry import Retry
from redis.sentinel import Sentinel


def _parse_sentinels(value):
    sentinels = []
    for item in value.split(","):
        host, separator, raw_port = item.strip().rpartition(":")
        if not separator or not host:
            raise ValueError("Элементы REDIS_SENTINELS должны иметь формат host:port.")
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("Порты Sentinel должны быть целыми числами.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Порт Sentinel должен находиться в диапазоне от 1 до 65535.")
        sentinels.append((host, port))
    if not sentinels:
        raise ValueError("Укажите хотя бы один адрес Redis Sentinel.")
    return sentinels


def _retry_policy(retries):
    return Retry(ExponentialBackoff(base=0.1, cap=0.5), retries=retries)


class RedisAccess:
    def __init__(self, sentinels, master_name, socket_timeout=2.0, socket_connect_timeout=2.0,
                 retries=3, read_from_replicas=True):
        sentinel_options = {
            "socket_timeout": socket_timeout,
            "socket_connect_timeout": socket_connect_timeout,
            "retry": _retry_policy(retries),
        }
        client_options = {
            "decode_responses": True,
            "socket_timeout": socket_timeout,
            "socket_connect_timeout": socket_connect_timeout,
            "health_check_interval": 15,
            "retry": _retry_policy(retries),
        }
        self.sentinel = Sentinel(sentinels, sentinel_kwargs=sentinel_options, **client_options)
        self.master_name = master_name
        self.read_from_replicas = read_from_replicas
        self.writer = self.sentinel.master_for(master_name, **client_options)
        self.reader = self.sentinel.slave_for(master_name, **client_options)

    @classmethod
    def from_config(cls, config):
        return cls(
            sentinels=_parse_sentinels(config["REDIS_SENTINELS"]),
            master_name=config["REDIS_MASTER_NAME"],
            socket_timeout=config["REDIS_SOCKET_TIMEOUT"],
            socket_connect_timeout=config["REDIS_SOCKET_CONNECT_TIMEOUT"],
            retries=config["REDIS_RETRY_COUNT"],
            read_from_replicas=config["REDIS_READ_FROM_REPLICAS"],
        )

    def ping(self):
        return self.writer.ping()

    def read(self, operation):
        if self.read_from_replicas:
            try:
                return operation(self.reader)
            except RedisError:
                # При запуске или переключении Sentinel может временно не иметь исправных реплик
                pass
        return operation(self.writer)

    def close(self):
        self.sentinel.close()
