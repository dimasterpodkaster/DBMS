"""HTTP-маршруты профилей игроков и фиксации входов"""

from flask import Blueprint, current_app, jsonify

from app.services.players import change_level, get_player, upsert_player, upsert_players_batch
from app.errors import ApiError
from app.validation import (json_object, path_identifier, required_integer, required_string)


players_blueprint = Blueprint("players", __name__)


@players_blueprint.route("/players/<player_id>", methods=["POST"])
def save_player(player_id):
    player_id = path_identifier(player_id, "player_id")
    payload = json_object()
    name = required_string(payload, "name")
    level = required_integer(payload, "level")
    region = required_string(payload, "region")
    created, player = upsert_player(current_app.extensions["redis_access"], player_id, name, level, region)
    return jsonify(player), 201 if created else 200


@players_blueprint.route("/players/<player_id>", methods=["GET"])
def read_player(player_id):
    player_id = path_identifier(player_id, "player_id")
    player = get_player(current_app.extensions["redis_access"], player_id)
    return jsonify(player)


@players_blueprint.route("/players/<player_id>/level", methods=["PATCH"])
def update_player_level(player_id):
    player_id = path_identifier(player_id, "player_id")
    payload = json_object()
    delta = required_integer(payload, "delta")
    result = change_level(current_app.extensions["redis_access"], player_id, delta)
    return jsonify(result)


@players_blueprint.route("/players/<player_id>/login", methods=["POST"])
def record_player_login(player_id):
    player_id = path_identifier(player_id, "player_id")
    result = current_app.extensions["login_counter"].increment(player_id)
    return jsonify(result)


@players_blueprint.route("/players/batch", methods=["POST"])
def save_players_batch():
    payload = json_object()
    raw_players = payload.get("players")
    if not isinstance(raw_players, list) or not raw_players:
        raise ApiError(400, "invalid_players", "players должен быть непустым массивом.")
    if len(raw_players) > 1000:
        raise ApiError(400, "invalid_players", "За один запрос можно загрузить не более 1000 профилей.")

    players = []
    seen_ids = set()
    for raw_player in raw_players:
        if not isinstance(raw_player, dict):
            raise ApiError(400, "invalid_player", "Каждый элемент players должен быть объектом.")
        player = {
            "id": required_string(raw_player, "id"),
            "name": required_string(raw_player, "name"),
            "level": required_integer(raw_player, "level"),
            "region": required_string(raw_player, "region"),
        }
        if player["id"] in seen_ids:
            raise ApiError(400, "duplicate_player_id", "Идентификаторы игроков в пакете должны быть уникальными.")
        seen_ids.add(player["id"])
        players.append(player)

    result = upsert_players_batch(current_app.extensions["redis_access"], players)
    return jsonify(result)
