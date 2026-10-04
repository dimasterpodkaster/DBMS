"""Атомарный счётчик входов с периодом хранения 24 часа"""


LOGIN_COUNTER_LUA = """
local count = redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[1])
return {count, redis.call('TTL', KEYS[1])}
"""

LOGIN_TTL_SECONDS = 24 * 60 * 60


class LoginCounter:
    def __init__(self, redis_client):
        self._redis = redis_client
        self._script = redis_client.register_script(LOGIN_COUNTER_LUA)

    def increment(self, player_id):
        key = "logins:{}".format(player_id)
        count, ttl = self._script(keys=[key], args=[LOGIN_TTL_SECONDS], client=self._redis)
        return {"player_id": player_id, "count": int(count), "ttl_seconds": int(ttl)}
