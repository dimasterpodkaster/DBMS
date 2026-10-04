"""Чтение уведомлений из Redis Streams и подтверждение обработки"""

import logging
import os
import time

from redis.exceptions import RedisError

from app.config import load_config
from app.redis_client import RedisAccess
from app.services.notifications import (NOTIFICATIONS_GROUP, NOTIFICATIONS_STREAM, ensure_notifications_group)


LOGGER = logging.getLogger("gamehub.notifications")
CONSUMER_NAME = os.getenv("NOTIFICATIONS_CONSUMER", "notifications-worker-1")
BATCH_SIZE = 20
POLL_INTERVAL_SECONDS = 0.5


def _handle_messages(redis_client, streams):
    for _, messages in streams:
        for event_id, fields in messages:
            LOGGER.info("Обработано событие %s для игрока %s: %s", event_id,
                        fields.get("player_id", "неизвестно"), fields.get("type", "без типа"))
            redis_client.xack(NOTIFICATIONS_STREAM, NOTIFICATIONS_GROUP, event_id)


def _contains_messages(streams):
    return bool(streams) and any(messages for _, messages in streams)


def run_worker():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    redis_access = RedisAccess.from_config(load_config())
    redis_access.ping()
    redis_client = redis_access.writer
    ensure_notifications_group(redis_client)
    LOGGER.info("Потребитель %s запущен", CONSUMER_NAME)

    while True:
        try:
            # Сначала дочитываем неподтверждённые события этого потребителя после перезапуска.
            pending = redis_client.xreadgroup(
                NOTIFICATIONS_GROUP,
                CONSUMER_NAME,
                {NOTIFICATIONS_STREAM: "0-0"},
                count=BATCH_SIZE,
            )
            if _contains_messages(pending):
                _handle_messages(redis_client, pending)
                continue

            messages = redis_client.xreadgroup(
                NOTIFICATIONS_GROUP,
                CONSUMER_NAME,
                {NOTIFICATIONS_STREAM: ">"},
                count=BATCH_SIZE,
            )
            if _contains_messages(messages):
                _handle_messages(redis_client, messages)
            else:
                time.sleep(POLL_INTERVAL_SECONDS)
        except RedisError:
            LOGGER.exception("Ошибка Redis при чтении уведомлений; повтор через секунду")
            time.sleep(1)


if __name__ == "__main__":
    run_worker()
