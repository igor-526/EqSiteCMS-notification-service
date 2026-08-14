# Notification Service

Сервис уведомлений EqSiteCMS — обрабатывает события от backend и формирует команды на отправку уведомлений (email, push, SMS).

## Стек

- Python 3.14.6
- FastAPI
- SQLAlchemy Core + asyncpg
- PostgreSQL 17
- Alembic
- NATS JetStream
- Sentry (опционально)

## Архитектура

```text
src/
├── clients/
│   └── nats/
│       ├── client.py              # NatsJetstreamClient
│       ├── publisher.py           # NotificationCommandsSendEmailEventPublisher
│       ├── consumers/             # Потребители событий
│       └── handlers/              # Обработчики событий
├── containers/                    # DI-контейнер
├── core/                          # Бизнес-логика и схемы
├── depends/                       # Зависимости FastAPI
├── models/                        # SQLAlchemy модели
├── repositories/                  # Реализации репозиториев
├── migration/                     # Alembic
├── utils/                         # Утилиты
├── main.py
└── settings.py
```

## Запуск в Docker

```bash
cp .env.example .env
docker compose up --build
```

Compose дождётся PostgreSQL и NATS, применит миграции и запустит сервис.

## Локальная разработка

```bash
cp .env.example .env
uv sync
docker compose up -d db nats
uv run alembic -c src/alembic.ini upgrade head
uv run uvicorn main:app --app-dir src --reload
```

```bash
make format
make lint
make test
```

## API

| Метод | Путь | Назначение | Доступ |
|-------|------|------------|--------|
| GET | `/health` | Healthcheck | Public |

## NATS JetStream

Notification Service выступает в роли **Pub/Sub** — потребляет события из `SITE_EVENTS` и публикует команды в `NOTIFICATION_COMMANDS`.

| Stream | Subject | Назначение | Роль |
|--------|---------|------------|------|
| SITE_EVENTS | events.site.callback.requested | Получение события запроса обратного звонка | входящий |
| NOTIFICATION_COMMANDS | commands.notification.email.send | Команда на отправку email уведомления | исходящий |

### Конфигурация

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `NATS_SERVERS` | Список серверов NATS (через запятую) | `nats://localhost:4222` |
| `NATS_STREAM_SITE_EVENTS` | Имя stream для событий сайта | `SITE_EVENTS` |
| `NATS_STREAM_NOTIFICATION_COMMANDS` | Имя stream для команд уведомлений | `NOTIFICATION_COMMANDS` |
| `NATS_SUBJECT_CALLBACK_REQUESTED` | Subject для событий обратного звонка | `events.site.callback.requested` |
| `NATS_SUBJECT_NOTIFICATION_COMMANDS_SEND_EMAIL` | Subject для команд отправки email | `commands.notification.email.send` |
| `NATS_CONSUMER_CALLBACK_REQUESTED` | Durable имя consumer | `notification-service-callback-requested` |
| `NATS_CONSUMER_ACK_WAIT_SECONDS` | Время ожидания ack (секунды) | `30` |
| `NATS_CONSUMER_MAX_DELIVER` | Максимум попыток доставки | `5` |

Sentry включается через `SENTRY_ENABLED=true` и `SENTRY_DSN`.
