# Server bug registry

Единый реестр проблем, обнаруженных при E2E/integration/API тестировании
`tg_bot_server`. Каждая проблема получает стабильный ID и отдельную секцию.

## Правила реестра

- Новые проблемы добавлять только сюда; отдельные MD-файлы на каждый баг не создавать.
- Для каждой проблемы указывать status, priority, expected, actual, repro, root cause,
  связанный тест и criteria of closure.
- Production-баги не исправлять в рамках тестовой итерации без отдельного разрешения.
- Проблемный тест писать с ожидаемым поведением и помечать строгим `xfail`.
- Не менять assertion на фактическое ошибочное поведение.
- Проблемы тестовой инфраструктуры исправлять сразу и не регистрировать как server bug.
- После исправления production-баг должен стать XPASS; затем снять `xfail`, обновить
  секцию и перевести её в `RESOLVED` или удалить по правилам трекера.

## Формат секции

Для каждой новой проблемы использовать поля:

- ID;
- status: `OPEN`, `IN_PROGRESS`, `BLOCKED`, `RESOLVED`;
- priority;
- area;
- summary;
- expected behavior;
- actual behavior;
- endpoint/payload;
- reproduction steps;
- root cause;
- related xfail tests;
- scope of fix;
- closure criteria.

---

## SERVER-PAYMENT-001 — нечисловой `Amount` webhook приводит к HTTP 500

- Status: `RESOLVED`
- Priority: `P0`
- Area: server payment webhook

### Summary

`POST /api/payments/webhooks/tbank` принимает поле `Amount` внешнего webhook
payload. Для успешного webhook route проверяет только, что значение является
`int` или `str`, а затем выполняет `int(amount)`. Для нечисловой строки возникает
необработанный `ValueError`.

### Expected behavior

Невалидный `Amount` должен приводить к контролируемому HTTP 400. Webhook не должен
применяться; заказ должен остаться в `waiting_payment`; payment не должен стать
`succeeded`; status history и notifications не должны измениться.

### Actual behavior

При валидных terminal/signature и payload с `"Amount": "not-an-integer"` server
возвращает HTTP 500 Internal Server Error.

Причина: `int(amount)` выбрасывает `ValueError`, который не преобразуется в
application/presentation error.

### Endpoint and payload

```http
POST /api/payments/webhooks/tbank
Content-Type: application/json
```

```json
{
  "TerminalKey": "test-terminal",
  "OrderId": "<payment-id>",
  "Success": true,
  "Status": "CONFIRMED",
  "PaymentId": "<provider-payment-id>",
  "Amount": "not-an-integer",
  "Date": "2026-01-01T10:00:00Z",
  "Token": "<valid-tbank-token>"
}
```

`Token` должен быть валидным. `OrderId` — внутренний `payment.id`, а
`PaymentId` — внешний `provider_payment_id`.

### Reproduction steps

1. Поднять server E2E Compose stack.
2. Создать customer и performer через API.
3. Создать direct-заказ.
4. Принять direct match и получить payment attempt.
5. Получить `provider_payment_id` попытки.
6. Сформировать валидную T-Bank подпись.
7. Заменить `Amount` на `not-an-integer`.
8. Отправить payload на `/api/payments/webhooks/tbank`.
9. Получить HTTP 500 вместо HTTP 400.

Команда:

```bash
uv run --directory tg_bot_server pytest \
  tests/e2e/test_payment_webhook_flow.py \
  -k 'invalid_payload and payload_update2'
```

Полный запуск:

```bash
make -C tg_bot_server test-e2e
```

### Related xfail tests

Файл: `tests/e2e/test_payment_webhook_flow.py`

Тест: `test_payment_webhook_rejects_invalid_payload[<Amount>-400]` — `xfail`
снят после исправления.

### Scope of fix

Исправление ограничить валидацией `Amount` в server webhook contract. Не менять
ожидаемый статус на 500, не принимать значение как нулевое, не игнорировать его
и не скрывать exception широким `except Exception` без корректного error mapping.

После исправления валидные суммы должны по-прежнему обрабатываться в копейках.

### Closure criteria

- HTTP 400 для нечислового `Amount` подтверждён;
- заказ остаётся `waiting_payment`;
- payment, status history и notifications не изменяются;
- unit, lint, type-check и E2E проверки выполнены;
- status секции обновлён на `RESOLVED`.

---

## SERVER-GEO-001 — неоднозначный ответ геокодера сохраняется как адрес

- Status: `OPEN`
- Priority: `P1`
- Area: server geocoding / performer addresses

### Summary

При создании адреса исполнителя backend сохраняет первый результат DaData,
даже если геокодер вернул несколько подсказок. Пользовательский flow требует
выбора конкретной подсказки до сохранения адреса.

### Expected behavior

При неоднозначном ответе геокодера backend должен вернуть контролируемую ошибку
валидации или потребовать явного выбора подсказки. Новая запись в `addresses` не
должна создаваться, а текущий адрес исполнителя не должен изменяться.

### Actual behavior

При ответе mock DaData с двумя подсказками backend возвращает HTTP `201 Created`
и сохраняет первую подсказку как новый адрес исполнителя.

### Endpoint and payload

```http
POST /api/performers/by-telegram/{telegram_id}/addresses
Content-Type: application/json
X-Service-Key: test-service-key
```

```json
{
  "city_id": "<active-city-id>",
  "unrestricted_value": "E2E_AMBIGUOUS"
}
```

Mock DaData отвечает двумя подсказками на
`POST /suggestions/api/4_1/rs/suggest/address`.

### Reproduction steps

1. Поднять server E2E Compose stack.
2. Создать и активировать performer с исходным рабочим адресом.
3. Запросить `/api/geocoding/address-suggestions` с query `E2E_AMBIGUOUS`.
4. Убедиться, что backend возвращает две подсказки.
5. Отправить `POST /api/performers/by-telegram/{telegram_id}/addresses` с
   `unrestricted_value: E2E_AMBIGUOUS`.
6. Наблюдать HTTP `201` и новую запись вместо HTTP `422` без изменения БД.

Команда:

```bash
make -C tg_bot_server test-e2e
```

### Root cause

`DaDataGeocoder.normalize()` вызывает `suggest(..., limit=1)` и без проверки
берёт первую подсказку. Use case создания адреса не требует подтверждения того,
что результат был однозначным.

### Related xfail tests

Файл: `tests/e2e/test_geocoding_negative.py`

Тест: `test_ambiguous_geocoding_result_is_not_saved`

Маркер:

```python
pytest.mark.xfail(
    strict=True,
    reason="Known server bug: ambiguous geocoding result is saved",
)
```

### Scope of fix

Согласовать normalize/create-address flow с user flow: неоднозначный результат
не должен автоматически превращаться в сохранённый адрес. Не менять assertion
на фактический HTTP `201` и не удалять проверку отсутствия записи.

### Closure criteria

- тест становится XPASS;
- `xfail` снят;
- неоднозначный результат больше не создаёт запись адреса;
- текущий адрес исполнителя не изменяется;
- пустой, timeout и HTTP 5xx сценарии продолжают проходить;
- секция переведена в `RESOLVED` или удалена после закрытия задачи.

---

## SERVER-WORKER-001 — истечение payment deadline падает на check constraint

- Status: `OPEN`
- Priority: `P0`
- Area: server worker / order expiration

### Summary

`DeadlinesWorkerJob._expire_waiting_payments` не может завершить обработку
просроченного заказа, потому что записывает значение `payment_deadline` в
`orders.expired_reason`, а PostgreSQL constraint разрешает другое значение.
После исключения worker завершается, транзакция откатывается, а заказ и payment
остаются в исходном состоянии.

### Expected behavior

Worker должен атомарно обработать просроченный `waiting_payment` заказ:

- payment переводится из `pending` в `expired`;
- selected match закрывается со статусом `expired` и причиной `payment_deadline`;
- при ещё действующем matching deadline заказ возвращается в `searching`;
- при истёкшем matching deadline заказ переходит в `expired` с допустимой
  причиной истечения;
- создаётся одна status history запись и одно уведомление;
- повторная итерация worker не создаёт повторных бизнесовых изменений.

### Actual behavior

Worker падает с `asyncpg.exceptions.CheckViolationError`:

```text
new row for relation "orders" violates check constraint "ck_orders_expired_reason"
```

В SQLAlchemy flush виден конфликт:

```text
expired_reason = 'payment_deadline'
```

Миграция разрешает только:

```text
matching_deadline_reached
no_performer_selected
payment_deadline_reached
no_direct_response
system_error
```

Из-за исключения worker process завершается. Тест наблюдает `waiting_payment` и
`pending` вместо ожидаемого перехода.

### Reproduction steps

1. Поднять Compose E2E stack.
2. Создать direct-заказ и принять match.
3. В тестовой подготовке выставить `orders.payment_deadline_at` в прошлое.
4. Для первой ветки выставить `matching_deadline_at` в будущее, для второй — в прошлое.
5. Дождаться итерации worker.
6. Наблюдать падение worker и отсутствие изменения состояния заказа.

Команда:

```bash
make -C tg_bot_server test-e2e
```

### Root cause

В `src/backend/worker/jobs.py` используется строка `payment_deadline`, которая
не совпадает с допустимым значением `payment_deadline_reached` из миграции
`20260713_0010_add_availability_order_schema.py`.

### Related xfail tests

Файл: `tests/e2e/test_payment_webhook_flow.py`

- `test_worker_expiring_payment_returns_order_to_searching`;
- `test_worker_expiring_payment_expires_order_after_matching_deadline`.

Оба теста помечены строгим `xfail` с ожидаемым бизнесовым поведением.

### Scope of fix

Согласовать значение `expired_reason` между worker и PostgreSQL constraint.
Не менять тестовые assertions на фактическое падение worker и не считать
завершением сценария остановившийся worker.

### Closure criteria

- worker не падает при обработке обеих веток payment deadline;
- разрешённое значение `expired_reason` соответствует утверждённому контракту;
- оба xfail-теста становятся XPASS, после чего `xfail` снимается;
- payment, match, order status history и notification проверяются повторно;
- полный `make -C tg_bot_server test-e2e` проходит.
