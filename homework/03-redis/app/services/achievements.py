"""Операции с достижениями игроков на основе Redis Set"""

from app.errors import ApiError


def add_achievement(redis_access, player_id, achievement_name):
    added = redis_access.writer.sadd("achievements:{}".format(player_id), achievement_name)
    return {"player_id": player_id, "achievement_name": achievement_name, "added": bool(added)}


def has_achievement(redis_access, player_id, achievement_name):
    present = redis_access.read(lambda redis: redis.sismember("achievements:{}".format(player_id),
                                                              achievement_name))
    return {"player_id": player_id, "achievement_name": achievement_name, "has_achievement": bool(present)}


def common_achievements(redis_access, player_id1, player_id2):
    names = redis_access.read(lambda redis: redis.sinter("achievements:{}".format(player_id1),
                                                         "achievements:{}".format(player_id2)))
    return {"player_ids": [player_id1, player_id2], "achievements": sorted(names)}
