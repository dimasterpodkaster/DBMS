"""HTTP-маршруты турнирной таблицы лидеров"""

from flask import Blueprint, current_app, jsonify, request

from app.errors import ApiError
from app.services.leaderboard import add_score, get_rank, get_top
from app.validation import json_object, path_identifier, required_number, required_string


leaderboard_blueprint = Blueprint("leaderboard", __name__)


@leaderboard_blueprint.route("/leaderboard/score", methods=["POST"])
def record_score():
    payload = json_object()
    player_id = required_string(payload, "player_id")
    score = required_number(payload, "score")
    result = add_score(
        current_app.extensions["redis_access"],
        player_id,
        score,
    )
    return jsonify(result)


@leaderboard_blueprint.route("/leaderboard/top", methods=["GET"])
def leaderboard_top():
    raw_limit = request.args.get("limit", "10")
    try:
        limit = int(raw_limit)
    except ValueError as exc:
        raise ApiError(400, "invalid_limit", "Параметр limit должен быть целым числом больше нуля.") \
            from exc
    if not 1 <= limit:
        raise ApiError(400, "invalid_limit", "Параметр limit должен быть целым числом больше нуля.")
    return jsonify(get_top(current_app.extensions["redis_access"], limit))


@leaderboard_blueprint.route("/leaderboard/rank/<player_id>", methods=["GET"])
def leaderboard_rank(player_id):
    player_id = path_identifier(player_id, "player_id")
    return jsonify(get_rank(current_app.extensions["redis_access"], player_id))
