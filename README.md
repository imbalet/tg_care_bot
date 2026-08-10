# tg_care_bot

Монорепозиторий сервиса для заказа услуг по уходу. В проект входят backend,
административный интерфейс, два Telegram-бота и локальные инфраструктурные
сервисы.

Backend является единственным владельцем бизнес-логики, данных и переходов
статусов. Telegram-боты являются тонкими клиентами: они управляют UI/FSM и
обращаются к backend по HTTP.

## Состав проекта

```text
tg_care_bot/
├── docker-compose.yml       # локальный полный стек
├── docker-compose.deploy.yml # стек из опубликованных образов
├── tg_bot_server/           # FastAPI backend, миграции и worker
├── tg_bot_customer/         # Telegram-бот заказчика
├── tg_bot_executor/         # Telegram-бот исполнителя
├── admin_ui/                # web-интерфейс администрирования
└── tbank_mock/              # локальный mock платёжного API
```

Основные runtime-сервисы:

- `postgres` — PostgreSQL, источник истины для бизнесовых данных;
- `redis` — FSM и краткоживущие технические данные;
- `minio` — локальное S3-совместимое хранилище файлов;
- `migrate` — однократное применение Alembic-миграций;
- `api` — HTTP API backend;
- `worker` — database-driven worker transactional outbox;
- `admin_web` — web-интерфейс админки;
- `customer_bot` — бот заказчика, включается профилем `bots`;
- `executor_bot` — бот исполнителя, включается профилем `bots`;
- `tbank_mock` — локальный платёжный mock, включается профилем
  `payment-mock`.

## Требования

Для запуска полного Docker-стека нужны:

- Docker Engine;
- Docker Compose v2 (`docker compose`);
- Git.

Для deployment-стека дополнительно нужен доступ к GHCR. Если пакеты приватные,
выполните `docker login ghcr.io` с GitHub token, имеющим `read:packages`.

Для запуска Python-компонентов и тестов вне Docker дополнительно нужны:

- Python версии, указанной в `.python-version` соответствующего проекта;
- `uv`;
- GNU Make;
- доступный Docker для integration и E2E-тестов.

Проверьте установку:

```bash
docker --version
docker compose version
uv --version
python --version
```

Сборка `tg_bot_server` загружает сертификаты российских удостоверяющих
центров на этапе Docker build. Для первой сборки необходим доступ к сети.

## Быстрый запуск полного локального стека

Все команды ниже выполняются из корня репозитория.

### 1. Создать конфигурацию

```bash
cp .env.example .env
```

Откройте `.env` и замените как минимум:

- `CUSTOMER_BOT_TOKEN` — token бота заказчика;
- `EXECUTOR_BOT_TOKEN` — token бота исполнителя;
- `SERVICE_KEY` — общий внутренний ключ backend и ботов;
- `DEFAULT_ADMIN_PASSWORD` — пароль первоначального администратора.

Для запуска только backend-стека Telegram tokens можно оставить пустыми и не
включать профиль `bots`. Значения `TBANK_TERMINAL_KEY` и `TBANK_PASSWORD` нужны
для платёжных сценариев. Для обычного старта API они должны быть заданы, даже
если платежи пока не используются.

Не добавляйте `.env` в Git и не публикуйте реальные tokens, passwords или API
keys.

### 2. Проверить конфигурацию Compose

До запуска полезно проверить, что все обязательные переменные определены:

```bash
docker compose --env-file .env config
```

Если Compose сообщает, что переменная `... is required`, задайте её в `.env` и
повторите проверку.

### 3. Запустить backend и инфраструктуру

```bash
docker compose --env-file .env up -d --build
```

Эта команда запускает PostgreSQL, Redis, MinIO, миграции, API, worker и
административный web-интерфейс. Сервис `migrate` завершается после применения
миграций — это ожидаемое поведение.

### 4. Проверить состояние сервисов

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 api
```

API предоставляет health endpoints:

```bash
curl http://localhost:18000/health/live
curl http://localhost:18000/health/ready
```

Админка доступна по адресу:

```text
http://localhost:18001/
```

Первоначальные данные администратора берутся из `DEFAULT_ADMIN_EMAIL`,
`DEFAULT_ADMIN_FULL_NAME` и `DEFAULT_ADMIN_PASSWORD`. После первого входа
используйте безопасный пароль, отличный от локального примера.

### 5. Запустить Telegram-ботов

После заполнения обоих Telegram tokens:

```bash
docker compose --env-file .env --profile bots up -d --build
```

Проверить их логи можно отдельно:

```bash
docker compose --env-file .env logs -f customer_bot
docker compose --env-file .env logs -f executor_bot
```

Остановить просмотр логов можно сочетанием `Ctrl+C`; это не останавливает
контейнеры.

## Локальный платёжный mock

По умолчанию в `.env.example` указан тестовый URL T-Bank. Для полностью
изолированного локального сценария можно использовать `tbank_mock`.

В `.env` задайте настройки mock:

```dotenv
PAYMENT_PROVIDER=tbank_test
TBANK_BASE_URL=http://tbank_mock:8080/v2
TBANK_TERMINAL_KEY=mock-terminal
TBANK_PASSWORD=mock-password
TBANK_NOTIFICATION_URL=http://api:8000/api/payments/webhooks/tbank
TBANK_MOCK_PUBLIC_BASE_URL=http://localhost:18080
```

`http://tbank_mock:8080` — адрес внутри Docker Compose-сети. Адрес
`http://localhost:18080` предназначен для открытия mock-платёжной формы из
браузера.

Запустите backend, worker, mock и ботов одновременно:

```bash
docker compose --env-file .env \
  --profile payment-mock \
  --profile bots \
  up -d --build
```

Проверка mock:

```bash
curl http://localhost:18080/health
```

Если используется настоящий тестовый T-Bank API, не включайте профиль
`payment-mock` и укажите корректные sandbox credentials и публичный
`TBANK_NOTIFICATION_URL`, доступный платёжному провайдеру.

## Опубликованные порты

| Сервис | Адрес с хоста | Назначение |
|---|---|---|
| API | `http://localhost:18000` | Backend HTTP API |
| Admin UI | `http://localhost:18001` | Административная панель |
| PostgreSQL | `localhost:15432` | Подключение с хоста |
| Redis | `localhost:16379` | Подключение с хоста |
| MinIO API | `http://localhost:19000` | S3 API |
| MinIO Console | `http://localhost:19001` | Web-консоль MinIO |
| T-Bank mock | `http://localhost:18080` | Локальный платёжный mock |

Внутри Compose-сети сервисы обращаются друг к другу по именам сервисов и
внутренним портам. Например, backend использует `postgres:5432`, `redis:6379`
и `minio:9000`; значения `localhost:15432`, `localhost:16379` и
`localhost:19000` предназначены для программ, запущенных непосредственно на
хосте.

## MinIO

Сервис `minio_init` автоматически создаёт bucket из `S3_BUCKET` после запуска
MinIO. Для входа в консоль используйте:

```text
http://localhost:19001/
```

Credentials консоли задаются через `MINIO_ROOT_USER` и
`MINIO_ROOT_PASSWORD`. Bucket должен оставаться приватным; backend выдаёт
короткоживущие signed URL для доступа к файлам.

## Управление стеком

Показать состояние:

```bash
docker compose --env-file .env ps
```

Следить за всеми логами:

```bash
docker compose --env-file .env logs -f
```

Следить за одним сервисом:

```bash
docker compose --env-file .env logs -f api
docker compose --env-file .env logs -f worker
docker compose --env-file .env logs -f postgres
```

Пересобрать один сервис:

```bash
docker compose --env-file .env build api
docker compose --env-file .env up -d api
```

Остановить контейнеры, сохранив volumes:

```bash
docker compose --env-file .env down
```

Остановить контейнеры и удалить локальные volumes:

```bash
docker compose --env-file .env down -v --remove-orphans
```

Последняя команда удаляет локальные данные PostgreSQL, Redis, MinIO и mock
платежей. Используйте её только если данные больше не нужны.

## Сборка и deployment образов через GitHub Actions

Workflow `.github/workflows/docker-images.yml` собирает пять образов:

- `server`;
- `customer`;
- `executor`;
- `admin-ui`;
- `tbank-mock`.

Pull request проверяет сборку без публикации. Каждый push публикует образы в
GHCR с SHA-тегом и тегом ветки. Для default branch дополнительно обновляется
`latest`, а Git-теги вида `v1.2.3` получают version-теги.

Для запуска уже собранных образов скопируйте deployment-конфигурацию:

```bash
cp .env.deploy.example .env.deploy
```

В `.env.deploy.example` уже перечислены все переменные deployment-стека.
Скопируйте файл и замените все значения `replace-with-*` реальными секретами.
Координаты образов можно переопределить, например:

```dotenv
IMAGE_NAMESPACE=ghcr.io/imbalet/tg_care_bot
IMAGE_TAG=sha-0123456789abcdef
```

Запуск выполняется без сборки:

```bash
docker compose -f docker-compose.deploy.yml --env-file .env.deploy pull
docker compose -f docker-compose.deploy.yml --env-file .env.deploy up -d
```

Telegram-боты запускаются профилем `bots`:

```bash
docker compose -f docker-compose.deploy.yml \
  --env-file .env.deploy --profile bots up -d
```

Локальный T-Bank mock запускается отдельно профилем `payment-mock`; в
production используйте внешний платёжный API.

Deployment Compose содержит self-hosted PostgreSQL, Redis и MinIO. Перед
production-эксплуатацией настройте резервное копирование PostgreSQL, TLS и
ограничение доступа к серверу. Для отката задайте предыдущий SHA-тег в
`IMAGE_TAG` и снова выполните `pull` и `up -d`.

## Переменные окружения

Корневой `.env.example` является конфигурацией для repository-level Compose.
Ключевые группы настроек:

| Группа | Переменные | Назначение |
|---|---|---|
| Приложение | `APP_ENV`, `APP_NAME`, `LOG_LEVEL` | Режим и журналирование |
| PostgreSQL | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | База данных |
| Redis | `REDIS_PASSWORD` | Техническое хранилище и FSM |
| Internal auth | `SERVICE_KEY` | Аутентификация bot-to-backend |
| Worker | `WORKER_POLL_INTERVAL_SECONDS`, `WORKER_BATCH_LIMIT` | Обработка outbox |
| MinIO | `MINIO_ROOT_*` | Администратор локального MinIO |
| S3 | `S3_*` | Доступ backend к object storage |
| Telegram | `CUSTOMER_BOT_TOKEN`, `EXECUTOR_BOT_TOKEN`, `TELEGRAM_*` | Работа ботов и уведомлений |
| Геокодинг | `DADATA_*` | DaData API |
| Платежи | `PAYMENT_PROVIDER`, `TBANK_*` | T-Bank или локальный mock |
| Чеки | `PAYMENT_RECEIPT_*` | Параметры платёжных чеков |
| Админка | `DEFAULT_ADMIN_*` | Первоначальный администратор |

В `.env.example` есть комментарии к каждой переменной и безопасные значения для
локальной разработки. Пустые или placeholder credentials не подходят для
реальных внешних интеграций.

Важно различать два режима конфигурации:

- root `.env` используется Docker Compose;
- `tg_bot_server/.env`, `tg_bot_customer/.env` и `tg_bot_executor/.env`
  используются при запуске соответствующего проекта непосредственно на
  хосте.

## Запуск компонентов без Docker

Такой режим нужен для разработки конкретного компонента. PostgreSQL, Redis и
MinIO всё равно должны быть доступны. Удобнее всего сначала запустить
инфраструктуру Compose, а затем запускать Python-процессы на хосте.

### Backend

```bash
cd tg_bot_server
uv sync --all-groups
cp .env.example .env
uv run python -m backend.main
```

В другом терминале:

```bash
cd tg_bot_server
uv run python -m backend.worker.main
```

Для ручного применения миграций:

```bash
cd tg_bot_server
uv run alembic upgrade head
```

При host-based запуске значения `DB_HOST`, `REDIS_HOST` и `S3_ENDPOINT_URL`
должны указывать на опубликованные адреса хоста, например `localhost`,
`localhost:16379` и `http://localhost:19000` согласно формату каждой переменной.

### Customer bot

```bash
cd tg_bot_customer
uv sync --all-groups
cp .env.example .env
uv run python -m customer_bot.main
```

Укажите в его `.env` реальный `BOT_TOKEN`, адрес backend и credentials Redis.

### Executor bot

```bash
cd tg_bot_executor
uv sync --all-groups
cp .env.example .env
uv run python -m executor_bot.main
```

Боты не подключаются к PostgreSQL напрямую и не должны содержать бизнесовую
логику backend.

### T-Bank mock отдельно

```bash
cd tbank_mock
uv sync --all-groups
uv run uvicorn tbank_mock.app:app --host 0.0.0.0 --port 8080
```

Для backend, запущенного на хосте, в этом режиме используйте URL mock, который
доступен из host-процесса, например `http://localhost:18080/v2` после
публикации порта или запуска mock на соответствующем порту.

## Миграции и начальные данные

В Docker миграции применяются сервисом `migrate` автоматически перед стартом
API и worker:

```bash
docker compose --env-file .env logs migrate
```

При ручном запуске backend:

```bash
cd tg_bot_server
uv run alembic upgrade head
```

Откатить одну миграцию:

```bash
cd tg_bot_server
uv run alembic downgrade -1
```

Миграции рассчитаны на PostgreSQL. SQLite не используется для проверки
персистентности приложения. Начальные миграции создают первоначального
администратора и seed-данные MVP-каталога на основании переменных
`DEFAULT_ADMIN_*`.

## Проверки и тесты

Каждый Python-проект использует `uv`. Не устанавливайте зависимости через
`pip` напрямую.

### Server

```bash
make -C tg_bot_server lint
make -C tg_bot_server test
make -C tg_bot_server test-unit
make -C tg_bot_server test-api
make -C tg_bot_server test-integration
make -C tg_bot_server test-e2e
make -C tg_bot_server test-all
```

`test` запускает изолированные unit и API-тесты. Integration и E2E-тесты
поднимают отдельный Docker Compose-стек с PostgreSQL, Redis, MinIO и mock
внешних сервисов.

Полная локальная проверка включает форматирование, Ruff, mypy, compile check,
unit/API, integration и E2E. Для unit/API действует текущий coverage baseline;
его можно изменить, например:

```bash
make -C tg_bot_server COVERAGE_MIN=70 test-all
```

Для сохранения test databases после неудачного integration-прогона:

```bash
KEEP_TEST_DATABASES=1 make -C tg_bot_server test-integration
```

Очистить тестовую инфраструктуру:

```bash
make -C tg_bot_server test-clean
```

При отладке test Compose:

```bash
docker compose -f tg_bot_server/docker-compose.test.yml logs
```

### Customer и executor

```bash
make -C tg_bot_customer lint
uv run --directory tg_bot_customer pytest

make -C tg_bot_executor lint
uv run --directory tg_bot_executor pytest
```

Unit-тесты не должны обращаться к реальным Telegram, PostgreSQL, Redis,
платёжному API, S3 или DaData. Для integration/E2E используются отдельные
тестовые сервисы и mock-адаптеры.

## Типовые проблемы

### Compose сообщает о missing required variable

Проверьте `.env` и итоговую конфигурацию:

```bash
docker compose --env-file .env config
```

Обязательные значения помечены в `docker-compose.yml` синтаксисом
`${VARIABLE:?VARIABLE is required}`.

### Порт уже занят

Проверьте занятый порт средствами ОС либо измените левую часть mapping в
`docker-compose.yml`. Внутренние порты контейнеров менять не требуется.

### API не стартует после изменения конфигурации

Посмотрите зависимости и логи:

```bash
docker compose --env-file .env ps
docker compose --env-file .env logs migrate api postgres redis
```

API начинает работу после успешного завершения `migrate` и health-checks
PostgreSQL/Redis.

### Бот сразу завершается

Проверьте token и логи конкретного контейнера:

```bash
docker compose --env-file .env logs customer_bot
docker compose --env-file .env logs executor_bot
```

Также убедитесь, что профиль `bots` был включён и `.env` был передан через
`--env-file` либо лежит в корне проекта.

### Платёжный mock недоступен

Проверьте профиль, адрес внутри Compose-сети и состояние mock:

```bash
docker compose --env-file .env --profile payment-mock ps
docker compose --env-file .env logs tbank_mock
curl http://localhost:18080/health
```

Backend внутри Docker должен использовать `http://tbank_mock:8080/v2`, а не
`localhost:18080`.

### После изменений используется старый образ

Пересоберите нужный сервис:

```bash
docker compose --env-file .env build --no-cache api
docker compose --env-file .env up -d api
```

### Docker Compose оставил orphan containers

```bash
docker compose --env-file .env up -d --remove-orphans
```

## Безопасность и ограничения

- Не коммитьте `.env`, tokens, passwords и внешние API keys.
- Не используйте локальные credentials в production.
- Не направляйте production backend на локальный MinIO или T-Bank mock.
- Административные действия проходят через application services и аудит.
- Telegram-боты не являются источником истины для заказов, платежей и
  статусов.
- Redis не заменяет PostgreSQL.
- Перед production-эксплуатацией отдельно настройте TLS, reverse proxy,
  секрет-хранилище, резервное копирование PostgreSQL и мониторинг.

Готовой production-конфигурации в этом репозитории нет; приведённые команды
предназначены для локальной разработки, проверки и тестирования.

## Дополнительная документация

- [Backend README](tg_bot_server/README.md)
- [Customer bot README](tg_bot_customer/README.md)
- [Executor bot README](tg_bot_executor/README.md)
- [T-Bank mock README](tbank_mock/README.md)
- [Техническая архитектура](04-technical-architecture-v1.1.md)
- [User flow](02-user-flow-v2.4.md)
- [Бизнес-правила](03-business-concept-and-rules-v2.4.md)
