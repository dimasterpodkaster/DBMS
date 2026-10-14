"""Операции с профилями игроков в Redis Hash и кэше"""

import json
import time
from datetime import datetime, timezone

from app.errors import ApiError
from app.services.notifications import (NOTIFICATIONS_STREAM, STREAM_RETENTION_SECONDS, ensure_notifications_group,
                                        stream_minimum_id)


PLAYER_CACHE_TTL_SECONDS = 60

UPSERT_PLAYER_LUA = """
local created = redis.call('HSETNX', KEYS[1], 'created_at', ARGV[5])
redis.call('HSET', KEYS[1], 'name', ARGV[2], 'level', ARGV[3], 'region', ARGV[4])
redis.call('DEL', KEYS[2])
local event_type = 'player_updated'
local message = 'Обновлён профиль игрока'
if created == 1 then
    event_type = 'player_created'
    message = 'Создан профиль игрока'
end
redis.call('XADD', KEYS[3], '*', 'player_id', ARGV[1], 'type', event_type, 'message', message, 'timestamp', ARGV[5])
redis.call('XTRIM', KEYS[3], 'MINID', ARGV[6])
redis.call('EXPIRE', KEYS[3], ARGV[7])
return {created, redis.call('HGETALL', KEYS[1])}
"""

CACHE_PLAYER_LUA = """
local cached = redis.call('GET', KEYS[2])
if cached then
    return cached
end
local fields = redis.call('HGETALL', KEYS[1])
if #fields == 0 then
    return nil
end
local profile = {id = ARGV[1]}
for index = 1, #fields, 2 do
    profile[fields[index]] = fields[index + 1]
end
profile.level = tonumber(profile.level)
local encoded = cjson.encode(profile)
redis.call('SET', KEYS[2], encoded, 'EX', ARGV[2])
return encoded
"""

CHANGE_LEVEL_LUA = """
if redis.call('HEXISTS', KEYS[1], 'name') == 0 then
    return nil
end
local level = redis.call('HINCRBY', KEYS[1], 'level', ARGV[1])
redis.call('DEL', KEYS[2])
redis.call('XADD', KEYS[3], '*', 'player_id', ARGV[2], 'type', 'level_changed',
           'message', 'Изменён уровень игрока', 'timestamp', ARGV[3])
redis.call('XTRIM', KEYS[3], 'MINID', ARGV[4])
redis.call('EXPIRE', KEYS[3], ARGV[5])
return level
"""


def _profile(player_id, fields):
    try:
        level = int(fields["level"])
        name = fields["name"]
        region = fields["region"]
        created_at = fields["created_at"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(500, "invalid_profile_data", "В сохранённом профиле не хватает данных или они повреждены.") \
            from exc
    return {"id": player_id, "name": name, "level": level, "region": region, "created_at": created_at}


def _now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _upsert_keys(player_id):
    return ["player:{}".format(player_id), "cache:player:{}".format(player_id), NOTIFICATIONS_STREAM]


def _upsert_arguments(player_id, name, level, region, timestamp):
    minimum_id = stream_minimum_id(int(time.time() * 1000))
    return [player_id, name, level, region, timestamp, minimum_id, STREAM_RETENTION_SECONDS]


def _parse_upsert_result(player_id, result):
    created, raw_fields = result
    fields = dict(zip(raw_fields[::2], raw_fields[1::2]))
    return int(created) == 1, _profile(player_id, fields)


def upsert_player(redis_access, player_id, name, level, region):
    redis = redis_access.writer
    ensure_notifications_group(redis)
    timestamp = _now_utc()
    result = redis.eval(UPSERT_PLAYER_LUA, 3, *_upsert_keys(player_id),
                        *_upsert_arguments(player_id, name, level, region, timestamp))
    return _parse_upsert_result(player_id, result)


def get_player(redis_access, player_id):
    encoded = redis_access.writer.eval(CACHE_PLAYER_LUA, 2, "player:{}".format(player_id),
                                       "cache:player:{}".format(player_id), player_id, PLAYER_CACHE_TTL_SECONDS)
    if encoded is None:
        raise ApiError(404, "player_not_found", "Игрок не найден.")
    try:
        fields = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ApiError(500, "invalid_profile_cache", "Кэш профиля повреждён.") from exc
    return _profile(player_id, fields)


def change_level(redis_access, player_id, delta):
    redis = redis_access.writer
    ensure_notifications_group(redis)
    timestamp = _now_utc()
    new_level = redis.eval(CHANGE_LEVEL_LUA, 3, "player:{}".format(player_id), "cache:player:{}".format(player_id),
                           NOTIFICATIONS_STREAM, delta, player_id, timestamp,
                           stream_minimum_id(int(time.time() * 1000)), STREAM_RETENTION_SECONDS)
    if new_level is None:
        raise ApiError(404, "player_not_found", "Игрок не найден.")
    return {"id": player_id, "delta": delta, "level": int(new_level)}


def upsert_players_batch(redis_access, players):
    redis = redis_access.writer
    ensure_notifications_group(redis)
    pipeline = redis.pipeline(transaction=False)
    prepared = []
    for player in players:
        timestamp = _now_utc()
        prepared.append((player["id"], timestamp))
        pipeline.eval(UPSERT_PLAYER_LUA, 3, *_upsert_keys(player["id"]),
                      *_upsert_arguments(player["id"], player["name"], player["level"], player["region"], timestamp))

    pipeline.execute()
    return {"processed_count": len(prepared), "player_ids": [player_id for player_id, _ in prepared]}
