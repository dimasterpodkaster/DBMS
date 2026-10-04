"""Операции с потоком уведомлений и группой потребителей"""

from redis.exceptions import ResponseError


NOTIFICATIONS_STREAM = "notifications"
NOTIFICATIONS_GROUP = "notifications-group"
STREAM_RETENTION_SECONDS = 7 * 24 * 60 * 60
STREAM_RETENTION_MILLISECONDS = STREAM_RETENTION_SECONDS * 1000


def ensure_notifications_group(redis_client):
    try:
        redis_client.xgroup_create(NOTIFICATIONS_STREAM, NOTIFICATIONS_GROUP, id="0-0", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise


def stream_minimum_id(now_milliseconds):
    cutoff = max(0, now_milliseconds - STREAM_RETENTION_MILLISECONDS)
    return "{}-0".format(cutoff)
