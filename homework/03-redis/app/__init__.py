"""Фабрика Flask-приложения для GameHub"""

from flask import Flask, jsonify
from redis.exceptions import RedisError
from werkzeug.exceptions import HTTPException

from app.config import load_config
from app.errors import ApiError
from app.redis_client import RedisAccess
from app.routes.achievements import achievements_blueprint
from app.routes.health import health_blueprint
from app.routes.leaderboard import leaderboard_blueprint
from app.routes.players import players_blueprint
from app.services.logins import LoginCounter
from app.services.notifications import ensure_notifications_group


HTTP_ERROR_MESSAGES = {
    400: "Некорректный HTTP-запрос.",
    404: "Запрошенный маршрут не найден.",
    405: "Метод запроса не поддерживается для этого маршрута.",
    413: "Размер тела запроса превышает допустимый предел.",
    415: "Для этого маршрута требуется JSON-запрос.",
}


def create_app(test_config=None, redis_access=None):
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if test_config:
        app.config.update(test_config)

    redis_access = redis_access or RedisAccess.from_config(app.config)
    if app.config["CHECK_REDIS_ON_START"]:
        try:
            redis_access.ping()
            ensure_notifications_group(redis_access.writer)
        except RedisError as exc:
            raise RuntimeError("Не удалось подключиться к Redis через Sentinel при запуске приложения.") from exc

    app.extensions["redis_access"] = redis_access
    app.extensions["login_counter"] = LoginCounter(redis_access.writer)

    app.register_blueprint(players_blueprint, url_prefix="/api")
    app.register_blueprint(leaderboard_blueprint, url_prefix="/api")
    app.register_blueprint(achievements_blueprint, url_prefix="/api")
    app.register_blueprint(health_blueprint, url_prefix="/api")

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify({"error": {"code": error.code, "message": error.message}}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        code = "not_found" if error.code == 404 else "http_error"
        message = HTTP_ERROR_MESSAGES.get(error.code, "Не удалось обработать HTTP-запрос.")
        return jsonify({"error": {"code": code, "message": message}}), error.code or 500

    @app.errorhandler(RedisError)
    def handle_redis_error(error):
        app.logger.warning("Ошибка Redis: %s", error)
        return jsonify({"error": {"code": "redis_unavailable", "message": "Redis временно недоступен."}}), 503

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Необработанная ошибка приложения")
        return jsonify({"error": {"code": "internal_error", "message": "Внутренняя ошибка сервера."}}), 500

    return app
