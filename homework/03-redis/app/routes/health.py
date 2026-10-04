"""Маршруты проверки работоспособности приложения и Redis"""

from flask import Blueprint, current_app, jsonify


health_blueprint = Blueprint("health", __name__)


@health_blueprint.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@health_blueprint.route("/ready", methods=["GET"])
def ready():
    current_app.extensions["redis_access"].ping()
    return jsonify({"status": "ready"})
