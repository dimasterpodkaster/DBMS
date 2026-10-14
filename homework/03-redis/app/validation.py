"""Общие простые проверки входных данных HTTP-запросов."""

import math

from flask import request

from app.errors import ApiError


def json_object():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError(400, "invalid_json", "Тело запроса должно быть JSON-объектом.")
    return payload


def required_string(payload, field):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "invalid_field", "Поле {} должно быть непустой строкой.".format(field))
    return value.strip()


def required_integer(payload, field):
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApiError(400, "invalid_field", "Поле {} должно быть целым числом.".format(field))
    return value


def required_number(payload, field):
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError(400, "invalid_field", "Поле {} должно быть числом.".format(field))
    if not math.isfinite(value):
        raise ApiError(400, "invalid_field", "Поле {} должно содержать конечное число.".format(field))
    return float(value)


def path_identifier(value, field="id"):
    if not value.strip():
        raise ApiError(400, "invalid_identifier", "Поле {} не должно быть пустым.".format(field))
    return value
