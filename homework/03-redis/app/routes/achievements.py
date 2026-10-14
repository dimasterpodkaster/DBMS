"""HTTP-маршруты достижений игроков"""

from flask import Blueprint, current_app, jsonify

from app.services.achievements import (add_achievement, common_achievements, has_achievement)
from app.validation import json_object, path_identifier, required_string


achievements_blueprint = Blueprint("achievements", __name__)


@achievements_blueprint.route("/players/<player_id>/achievements", methods=["POST"])
def create_achievement(player_id):
    player_id = path_identifier(player_id, "player_id")
    payload = json_object()
    achievement_name = required_string(payload, "achievement_name")
    result = add_achievement(current_app.extensions["redis_access"], player_id, achievement_name)
    return jsonify(result), 201 if result["added"] else 200


@achievements_blueprint.route("/players/<player_id>/achievements/<achievement_name>", methods=["GET"])
def check_achievement(player_id, achievement_name):
    player_id = path_identifier(player_id, "player_id")
    achievement_name = path_identifier(achievement_name, "achievement_name")
    result = has_achievement(current_app.extensions["redis_access"], player_id, achievement_name)
    return jsonify(result)


@achievements_blueprint.route("/players/<player_id1>/achievements/common/<player_id2>", methods=["GET"])
def find_common_achievements(player_id1, player_id2):
    player_id1 = path_identifier(player_id1, "player_id1")
    player_id2 = path_identifier(player_id2, "player_id2")
    result = common_achievements(current_app.extensions["redis_access"], player_id1, player_id2)
    return jsonify(result)
