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

- Status: `OPEN`
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

Тест: `test_payment_webhook_rejects_invalid_payload[<Amount>-400]`

Маркер:

```python
pytest.mark.xfail(
    strict=True,
    reason="Known server bug: non-numeric webhook amount returns 500",
)
```

### Scope of fix

Исправление ограничить валидацией `Amount` в server webhook contract. Не менять
ожидаемый статус на 500, не принимать значение как нулевое, не игнорировать его
и не скрывать exception широким `except Exception` без корректного error mapping.

После исправления валидные суммы должны по-прежнему обрабатываться в копейках.

### Closure criteria

- xfail-тест становится XPASS;
- `xfail` снят;
- HTTP 500 для нечислового `Amount` больше не воспроизводится;
- заказ остаётся `waiting_payment`;
- payment, status history и notifications не изменяются;
- unit/API/E2E проверки проходят;
- status секции обновлён на `RESOLVED`.
