"""Подготовка демонстрационных данных для Redis через HTTP API"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = os.getenv("GAMEHUB_API_URL", "http://127.0.0.1:5000/api").rstrip("/")
PROFILES = [
    {
        "id": str(1001 + index),
        "name": "Игрок {}".format(1001 + index),
        "level": 10 + index,
        "region": "RU" if index % 2 == 0 else "EU",
    }
    for index in range(10)
]


def request_json(method, path, payload=None):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(API_BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=5) as response:
            response_body = response.read()
    except HTTPError as error:
        try:
            error_body = json.loads(error.read().decode("utf-8"))
            message = error_body.get("error", {}).get("message", "подробности отсутствуют")
        except (ValueError, AttributeError):
            message = "подробности отсутствуют"
        raise RuntimeError(
            "Запрос {} {} завершился с HTTP {}: {}".format(method, path, error.code, message)
        ) from error
    except URLError as error:
        raise RuntimeError(
            "Не удалось подключиться к API по адресу {}. Проверьте, что сервис запущен.".format(API_BASE_URL)
        ) from error
    if not response_body:
        return None
    return json.loads(response_body.decode("utf-8"))


def prepare_data():
    request_json("GET", "/ready")
    batch_result = request_json("POST", "/players/batch", {"players": PROFILES})

    for index, profile in enumerate(PROFILES):
        request_json(
            "POST",
            "/leaderboard/score",
            {"player_id": profile["id"], "score": index * 100},
        )

    request_json(
        "POST",
        "/players/1001/achievements",
        {"achievement_name": "Первая победа"},
    )
    request_json(
        "POST",
        "/players/1001/achievements",
        {"achievement_name": "Исследователь"},
    )
    request_json(
        "POST",
        "/players/1002/achievements",
        {"achievement_name": "Первая победа"},
    )
    request_json("POST", "/players/1001/login")
    request_json("GET", "/players/1001")

    print("Подготовлены профили: {}".format(batch_result["processed_count"]))
    print("Начислены очки, добавлены достижения, зафиксирован вход игрока 1001.")
    print("Кэш профиля 1001 заполнен; изменение профилей создало события в notifications.")
    print("Повторный запуск добавляет очки к существующим значениям и увеличивает счётчик входов.")


if __name__ == "__main__":
    prepare_data()
