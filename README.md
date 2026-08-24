# Notification Service

Сервис уведомлений для EqSiteCMS. Обрабатывает события через NATS и формирует команды на доставку уведомлений.

Сервис использует опциональный Sentry и production Prometheus listener
`:9000/metrics` во внутренней Docker network. Общая матрица переменных,
sanitization, проверка и rollback описаны в
[`docs/operations/observability.md`](../../docs/operations/observability.md).

## Архитектура

### Слои

1. **Models** (`models/`) — SQLAlchemy таблицы
2. **Repositories** (`repositories/`) — CRUD операции с БД
3. **Services** (`core/services/`) — бизнес-логика и оркестрация
4. **Handlers** (`core/services/handlers/`) — обработка событий

### Сидирование данных

Сервис использует модуль сидирования (аналогично backend) для инициализации начальных данных:
- Каналы доставки (email, vk, sms)
- События (callback_request)

Сидирование происходит автоматически при старте приложения через `init_registry()`.

## Быстрый старт

### Установка зависимостей

```bash
uv sync
```

### Настройка окружения

Скопируйте `.env.example` в `.env` и заполните переменные:

```bash
cp .env.example .env
```

### Запуск

```bash
uv run uvicorn main:app --reload
```

### Миграции

```bash
# Применить миграции
uv run alembic upgrade head

# Создать новую миграцию
uv run alembic revision --autogenerate -m "description"
```

### Тесты

```bash
# Запустить все тесты
make test

# Запустить с линтингом
make lint

# Форматирование
make format
```

## Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `ENVIRONMENT` | Окружение | `development` |
| `DEBUG` | Режим отладки | `true` |
| `APP_TITLE` | Название приложения | `Notification Service` |
| `POSTGRES_USER` | Пользователь PostgreSQL | `app` |
| `POSTGRES_PASSWORD` | Пароль PostgreSQL | `app` |
| `POSTGRES_HOST` | Хост PostgreSQL | `localhost` |
| `POSTGRES_PORT` | Порт PostgreSQL | `5432` |
| `POSTGRES_DB` | Имя базы данных | `app` |
| `NATS_SERVERS` | Серверы NATS | `nats://localhost:4222` |
| `MAIN_BACKEND_URL` | URL main backend | `http://localhost:8000` |
| `MAIN_BACKEND_SERVICE_KEY` | Service key для main backend | - |

## API

### Health Check

```
GET /health
```

Ответ:
```json
{
  "status": "ok"
}
```

## Модели данных

### notification_channels

Каналы доставки уведомлений (email, vk, sms).

### notification_events

События, которые обрабатывает сервис.

### user_notification_settings

Настройки уведомлений пользователей.

## NATS

### Потребляемые события

- `events.site.callback.requested` — заявка на обратный звонок

### Публикуемые команды

- `commands.notification.email.send` — команда на отправку email
