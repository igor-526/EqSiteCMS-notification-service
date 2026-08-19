# Notification Service — Детальная документация

## Обзор

Notification Service — микросервис для обработки событий и формирования команд на доставку уведомлений.

## Архитектура

### Компоненты

```
┌─────────────────────────────────────────────────────────────┐
│                    Notification Service                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   NATS       │    │  Orchestrator│    │   Handlers   │  │
│  │  Consumer    │───▶│   Service    │───▶│  (Registry)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                    │          │
│         ▼                   ▼                    ▼          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Handler    │    │ Repositories │    │   Publisher  │  │
│  │  (Protocol)  │    │   (DB)       │    │   (NATS)     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Поток обработки события

1. **Получение события** — NATS Consumer получает событие
2. **Валидация** — Проверка структуры данных
3. **Поиск события в БД** — Получение metadata события
4. **Получение каналов** — Активные каналы доставки
5. **Поиск обработчика** — зарегистрированный в orchestrator обработчик по коду события
6. **Форматирование** — Обработчик формирует уведомление
7. **Публикация команды** — NATS Publisher отправляет команду

## Модели данных

### notification_channels

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Идентификатор канала |
| created_at | DateTime | Дата создания |
| updated_at | DateTime | Дата обновления |
| code | String(15) | Код канала (email, vk, sms) |
| name | String(31) | Название канала |
| description | String(511) | Описание канала |
| is_active | Boolean | Флаг активности |

### notification_events

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Идентификатор события |
| created_at | DateTime | Дата создания |
| updated_at | DateTime | Дата обновления |
| code | String(15) | Код события |
| name | String(31) | Название события |
| description | String(511) | Описание события |
| metadata | JSON | Метаданные для валидации |
| is_active | Boolean | Флаг активности |

### user_notification_settings

| Поле | Тип | Описание |
|------|-----|----------|
| id | UUID | Идентификатор настройки |
| created_at | DateTime | Дата создания |
| updated_at | DateTime | Дата обновления |
| user_id | UUID | ID пользователя |
| action_id | UUID | ID события (FK → notification_events) |
| channel_id | UUID | ID канала (FK → notification_channels) |

## Репозитории

### AbstractRepository

Базовый репозиторий с CRUD операциями:
- `get_by_id(id)` — получение по ID
- `get_all(limit, offset)` — получение всех
- `create(entity)` — создание
- `update(entity)` — обновление
- `delete(id)` — удаление

### ChannelRepository

- `get_by_code(code)` — получение канала по коду
- `get_active_channels()` — получение активных каналов

### EventRepository

- `get_by_code(code)` — получение события по коду
- `get_active_events()` — получение активных событий

### UserNotificationSettingRepository

- `get_by_user_and_event(user_id, action_id)` — настройки пользователя для события
- `get_users_by_event(action_id)` — все пользователи для события

## Сервисы

### NotificationOrchestratorService

Основной сервис оркестрации пайплайна обработки событий.

**Методы:**
- `register_handler(event_code, handler)` — регистрация обработчика
- `process_event(event_code, payload)` — обработка события

### CallbackEventHandler

Обработчик события "callback" (обратный звонок).

**Методы:**
- `format_notification(channel_code, payload, event)` — форматирование уведомления

## Сидирование

### Модуль utils/seeding/

- `BaseSeeder` — абстрактный базовый класс
- `SimpleSeeder` — generic seeder с дедупликацией по ID
- `ChannelSeeder` — seeder для каналов
- `EventSeeder` — seeder для событий

### Seed данные

**Каналы:**
- `email` — Электронная почта
- `vk` — VK
- `sms` — СМС

**События:**
- `callback` — Обратный звонок

## NATS

### Потребляемые потоки

- `SITE_EVENTS` — события сайта

### Публикуемые потоки

- `NOTIFICATION_COMMANDS` — команды на доставку

### Субъекты

- `events.site.callback.requested` — входящее событие
- `commands.notification.email.send` — команда на отправку email

## DI Container

### Регистрация компонентов

```python
class ApplicationContainer(containers.DeclarativeContainer):
    # NATS
    nats_client = providers.Singleton(NatsJetstreamClient, ...)
    notification_commands_send_email_publisher = providers.Singleton(...)

    # Repositories
    channel_repository = providers.Factory(ChannelRepository, ...)
    event_repository = providers.Factory(EventRepository, ...)
    user_notification_setting_repository = providers.Factory(...)

    # Services
    notification_orchestrator = providers.Singleton(NotificationOrchestratorService, ...)

    # Handlers
    # Единственный wired callback path: NATS consumer -> handler -> orchestrator.
    callback_request_handler = providers.Singleton(CallbackRequestHandler, ...)
```

## Тестирование

### Структура тестов

```
tests/
├── api/
│   └── test_health.py
├── unit/
│   ├── repositories/
│   │   ├── test_channel_repository.py
│   │   └── test_event_repository.py
│   └── services/
│       ├── test_callback_handler.py
│       └── test_notification_orchestrator.py
└── conftest.py
```

### Запуск тестов

```bash
make test
```

## Развертывание

### Docker

```dockerfile
FROM python:3.14-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen
COPY . .

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
services:
  notification-service:
    build: .
    environment:
      - POSTGRES_HOST=postgres
      - NATS_SERVERS=nats://nats:4222
      - MAIN_BACKEND_URL=http://backend:8000
    depends_on:
      - postgres
      - nats
```

## Мониторинг

### Health Check

```
GET /health
```

### Логирование

Логирование настраивается через `logging.basicConfig` в `main.py`.

## Будущие улучшения

1. Интеграция с main backend для получения пользователей
2. Circuit Breaker для main backend
3. Кеширование настроек пользователей
4. Метрики Prometheus
5. Distributed Tracing
