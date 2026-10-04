# Домашняя работа 1: Redis — GameHub

REST API сервиса GameHub на Python и Flask. Redis используется как основное хранилище, кэш и очередь уведомлений. Приложение будет находить текущий мастер через Sentinel.

## Целевая структура

- app — Flask-приложение.
- app/routes — HTTP-маршруты по областям API: игроки, входы, лидерборд и достижения.
- app/services — операции с Redis и бизнес-логика.
- app/workers — потребитель уведомлений из Redis Streams.
- openapi.yaml — контракт HTTP API.
- redis/redis.conf — настройки мастера.
- redis/replica-1.conf и redis/replica-2.conf — настройки двух реплик.
- redis/sentinel/ — конфиги и стартовый скрипт трех Sentinel.
- docker-compose.yml — Flask API и Redis-инфраструктура.
- Dockerfile — образ Flask API.
- requirements.txt — зависимости Python.
- dz1_check.py — скрипт самопроверки из задания.

## Docker Compose

Compose поднимает шесть Redis-контейнеров, Flask API и потребителя событий. Все опубликованные порты привязаны к localhost.

| Сервис | Порт на хосте | Порт в контейнере |
| --- | ---: | ---: |
| redis-master | 6379 | 6379 |
| redis-replica-1 | 6380 | 6379 |
| redis-replica-2 | 6381 | 6379 |
| sentinel-1 | 26379 | 26379 |
| sentinel-2 | 26380 | 26379 |
| sentinel-3 | 26381 | 26379 |
| api | 5000 | 5000 |
| notifications-worker | — | — |

Запускать Compose и скрипт самопроверки нужно из каталога homework/03-redis, чтобы команды docker compose нашли нужный файл:

    docker compose config
    docker compose up -d --build
    docker compose ps
    docker compose exec -T redis-master redis-cli INFO replication
    docker compose exec -T sentinel-1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster

API будет доступен по адресу http://127.0.0.1:5000. Приложение находит мастера через три Sentinel и отправляет ему записи. Обычные чтения направляются на реплики с fallback на мастер при ошибке соединения; кэш профилей читается и заполняется на мастере атомарно. Проверка Redis при старте завершает запуск приложения ошибкой, если Sentinel не находит мастер. Отдельный notifications-worker подключается к той же Redis-инфраструктуре.

Данные Redis и изменяемое состояние каждого Sentinel хранятся в отдельных именованных томах. Sentinel копирует свой шаблон конфигурации в том при первом запуске и затем сохраняет туда обнаруженное состояние. Изменение шаблона не переписывает уже созданный конфиг в томе. Для полного сброса локальных данных можно удалить тома командой docker compose down -v.

Проверка защиты от split-brain: приостановить обе реплики, подождать 10 секунд и попробовать записать ключ на мастере. Запись должна завершиться ошибкой NOREPLICAS; после проверки реплики нужно возобновить:

    docker compose pause redis-replica-1 redis-replica-2
    docker compose exec -T redis-master redis-cli SET splitbrain:probe value
    docker compose unpause redis-replica-1 redis-replica-2

## Контракт API

Реализованы профили игроков в Hash, счётчик входов с TTL, лидерборд в Sorted Set и достижения в Set. GET профиля использует cache-aside с TTL 60 секунд. Создание и изменение профиля атомарно инвалидируют кэш и добавляют событие в Stream. Фоновый потребитель читает группу notifications-group и подтверждает обработанные события через XACK. Stream хранит события не старше семи дней. Пакетный маршрут загружает профили через Redis pipeline.

Все запросы и ответы используют JSON. Время передается в UTC в формате RFC 3339. Идентификатор игрока — строка. Ошибки возвращаются в форме {"error": {"code": "...", "message": "..."}}.

| Метод | Путь | Назначение |
| --- | --- | --- |
| POST | /api/players/{id} | Создать или обновить профиль |
| GET | /api/players/{id} | Получить профиль через cache-aside |
| PATCH | /api/players/{id}/level | Изменить уровень на delta |
| POST | /api/players/{id}/login | Увеличить дневной счетчик входов |
| POST | /api/leaderboard/score | Начислить игроку очки турнира |
| GET | /api/leaderboard/top?limit=10 | Получить лидеров по убыванию очков |
| GET | /api/leaderboard/rank/{playerId} | Получить место игрока, начиная с 1 |
| POST | /api/players/{id}/achievements | Добавить достижение |
| GET | /api/players/{id}/achievements/{name} | Проверить наличие достижения |
| GET | /api/players/{id1}/achievements/common/{id2} | Получить общие достижения |
| POST | /api/players/batch | Массово создать профили через pipeline |
| GET | /api/health | Проверить, что процесс приложения работает |
| GET | /api/ready | Проверить доступность Redis через Sentinel |

### Форматы запросов

- Профиль: name, level, region. created_at назначает сервер при первом создании и сохраняет при обновлении.
- Изменение уровня: delta — целое число, которое прибавляется к текущему уровню.
- Вход: тело запроса не требуется; ответ содержит счетчик и оставшийся TTL.
- Очки: player_id и score. score прибавляется к текущей сумме игрока.
- Достижение: achievement_name.
- Массовая загрузка: объект с массивом players размером от 1 до 1000; каждый элемент содержит id, name, level и region. Для демонстрации pipeline загрузить не менее 10 профилей.

POST профиля возвращает 201 при создании и 200 при обновлении. Неизвестный профиль для GET и PATCH возвращает 404. Место в лидерборде нумеруется с 1, начиная с наибольшего результата; для этого API использует ZREVRANK.

## Ключи Redis

| Ключ | Тип | Содержимое и срок хранения |
| --- | --- | --- |
| player:{id} | Hash | name, level, region, created_at; без TTL |
| logins:{id} | String | Счетчик входов; TTL 24 часа, счетчик и TTL меняются атомарно |
| cache:player:{id} | String | JSON профиля; TTL 60 секунд |
| tournament:main | Sorted Set | member — player_id, score — очки |
| achievements:{id} | Set | Названия уникальных достижений игрока |
| notifications | Stream | player_id, type, message, timestamp; срок хранения 7 дней |

Группа notifications-group создаётся автоматически. Compose запускает отдельный notifications-worker, который после обработки подтверждает события через XACK; при перезапуске он дочитывает неподтверждённые сообщения своего потребителя.

## Ошибки и поведение

- 400 — некорректное тело или параметры запроса.
- 404 — профиль или место игрока не найдено.
- 503 — Redis/Sentinel временно недоступен.
- Ответ списка лидерборда содержит limit и массив элементов с player_id, score и rank.
- Ответ массовой загрузки содержит количество обработанных профилей и их идентификаторы.

Полное описание параметров, схем и ответов приведено в [openapi.yaml](openapi.yaml).

## Совместимость с самопроверкой

Для подготовки данных запустите из каталога homework/03-redis:

    docker compose up -d --build --wait
    python seed_data.py
    python dz1_check.py

Скрипт seed_data.py создаёт 10 профилей через пакетный API, добавляет игроков в лидерборд, сохраняет достижения, фиксирует вход игрока 1001 и заполняет его кэш. Сохранение профилей автоматически добавляет события в notifications; consumer group создаётся приложением, а worker подтверждает обработку. Повторный запуск безопасен для профилей и достижений, но добавляет очки к лидерборду и увеличивает счётчик входов.

Самопроверка использует сервисы redis-master и sentinel-1, а имя мастера Sentinel — mymaster. Она проверяет профиль player:1001, лидерборд tournament:main, достижения achievements:1001, кэш cache:player:1001, счётчик logins:1001, Stream notifications, consumer group notifications-group, не менее 10 профилей, защиту от split-brain и AOF.
