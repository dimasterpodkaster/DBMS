"""Операции с турнирной таблицей на основе Redis Sorted Set"""

from app.errors import ApiError


LEADERBOARD_KEY = "tournament:main"


def add_score(redis_access, player_id, score):
    total = redis_access.writer.zincrby(LEADERBOARD_KEY, score, player_id)
    return {"player_id": player_id, "score": total}


def get_top(redis_access, limit):
    rows = redis_access.read(lambda redis: redis.zrevrange(LEADERBOARD_KEY, 0, limit - 1, withscores=True))
    items = [{"player_id": player_id, "score": score, "rank": index}
             for index, (player_id, score) in enumerate(rows, start=1)]
    return {"limit": limit, "items": items}


def get_rank(redis_access, player_id):
    def read_rank(redis):
        score = redis.zscore(LEADERBOARD_KEY, player_id)
        rank = redis.zrevrank(LEADERBOARD_KEY, player_id)
        return score, rank

    score, rank = redis_access.read(read_rank)
    if score is None or rank is None:
        raise ApiError(404, "player_not_ranked", "Игрок отсутствует в таблице лидеров.")
    return {"player_id": player_id, "score": score, "rank": rank + 1}
