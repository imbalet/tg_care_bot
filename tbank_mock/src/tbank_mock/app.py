import asyncio
import html
import json
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .cards import CardScenario, get_scenario
from .config import Settings
from .signatures import sign_payload, verify_payload
from .store import PaymentStore


settings = Settings.from_env()
store = PaymentStore(settings.database_path)
app = FastAPI(title="T-Bank Mock API", version="0.1.0")
_webhook_dispatcher_task: asyncio.Task[None] | None = None


def _error(message: str, code: str = "1030", status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        {
            "Success": False,
            "ErrorCode": code,
            "Message": message,
            "Details": message,
        },
        status_code=status_code,
    )


def _validate_request(payload: dict[str, Any]) -> str | None:
    if str(payload.get("TerminalKey")) != settings.terminal_key:
        return "Неверный терминал"
    if not verify_payload(payload, settings.password):
        return "Неверный токен. Проверьте пару TerminalKey/SecretKey"
    return None


def _parse_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _request_amount(payload: dict[str, Any], fallback: int) -> int | None:
    if "Amount" not in payload:
        return fallback
    return _parse_positive_int(payload["Amount"])


def _payment_response(payment: Any) -> dict[str, Any]:
    return {
        "Success": True,
        "ErrorCode": "0",
        "TerminalKey": payment["terminal_key"],
        "PaymentId": str(payment["id"]),
        "OrderId": payment["order_id"],
        "Status": payment["status"],
        "Amount": payment["amount"],
        "Date": payment["created_at"],
        "PaymentDate": payment["updated_at"],
    }


def _webhook_payload(payment: Any, status: str, amount: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "TerminalKey": payment["terminal_key"],
        "OrderId": payment["order_id"],
        "Success": status in {"AUTHORIZED", "CONFIRMED"},
        "Status": status,
        "PaymentId": str(payment["id"]),
        "ErrorCode": payment["last_error_code"],
        "Amount": amount,
        "Date": payment["created_at"],
        "PaymentDate": payment["updated_at"],
    }
    payload["Token"] = sign_payload(payload, settings.password)
    return payload


async def _deliver_webhook(delivery_id: int, *, already_claimed: bool = False) -> None:
    if not already_claimed and not store.claim_webhook(delivery_id):
        return
    delivery = store.get_webhook_delivery(delivery_id)
    if delivery is None:
        return
    payment = store.get_payment(str(delivery["payment_id"]))
    if payment is None or not payment["notification_url"]:
        store.mark_webhook_delivered(delivery_id)
        return
    payload = json.loads(delivery["payload_json"])
    for attempt in range(delivery["attempts"] + 1, settings.webhook_retry_count + 1):
        status_code: int | None = None
        error: str | None = None
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                response = await client.post(payment["notification_url"], json=payload)
            status_code = response.status_code
            if 200 <= status_code < 300:
                store.record_webhook_attempt(delivery_id, attempt, status_code, None)
                store.mark_webhook_delivered(delivery_id)
                return
            error = f"HTTP {status_code}"
        except httpx.HTTPError as exc:
            error = str(exc)[:500]
        store.record_webhook_attempt(delivery_id, attempt, status_code, error)
        if attempt < settings.webhook_retry_count:
            await asyncio.sleep(settings.webhook_retry_delay_seconds)
    store.reschedule_webhook(
        delivery_id,
        utc_now() + timedelta(seconds=settings.webhook_retry_delay_seconds),
        error or "webhook delivery failed",
        permanently_failed=True,
    )


async def _webhook_dispatcher() -> None:
    while True:
        delivery_ids = store.claim_due_webhooks()
        for delivery_id in delivery_ids:
            await _deliver_webhook(delivery_id, already_claimed=True)
        await asyncio.sleep(min(settings.webhook_retry_delay_seconds, 1))


@app.on_event("startup")
async def start_webhook_dispatcher() -> None:
    global _webhook_dispatcher_task
    store.recover_processing_webhooks()
    _webhook_dispatcher_task = asyncio.create_task(_webhook_dispatcher())


@app.on_event("shutdown")
async def stop_webhook_dispatcher() -> None:
    global _webhook_dispatcher_task
    if _webhook_dispatcher_task is not None:
        _webhook_dispatcher_task.cancel()
        with suppress(asyncio.CancelledError):
            await _webhook_dispatcher_task
        _webhook_dispatcher_task = None


def _queue_webhook(background_tasks: BackgroundTasks, payment: Any, status: str, amount: int) -> None:
    if not payment["notification_url"]:
        return
    delivery_id = store.enqueue_webhook(
        payment["id"],
        status,
        amount,
        _webhook_payload(payment, status, amount),
    )
    if delivery_id is not None:
        background_tasks.add_task(_deliver_webhook, delivery_id)


def _valid_card_input(
    pan: str,
    exp_date: str,
    cvv: str,
    cardholder: str,
) -> bool:
    digits = "".join(character for character in pan if character.isdigit())
    if len(digits) != 16 or not cvv.isdigit() or len(cvv) not in {3, 4}:
        return False
    if not cardholder.strip() or "/" not in exp_date:
        return False
    month_text, year_text = exp_date.strip().split("/", 1)
    if not month_text.isdigit() or not year_text.isdigit():
        return False
    month = int(month_text)
    year = int(year_text)
    if not 1 <= month <= 12:
        return False
    if len(year_text) == 2:
        year += 2000
    now = datetime.now(UTC)
    return (year, month) >= (now.year, now.month)


def _failure_response(payment: Any, title: str, message: str) -> HTMLResponse:
    if payment["fail_url"]:
        return RedirectResponse(payment["fail_url"], status_code=303)
    return _page(title, message)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v2/Init")
async def init_payment(request: Request) -> JSONResponse:
    payload = await request.json()
    error = _validate_request(payload)
    if error:
        return _error(error, "204")
    amount = _parse_positive_int(payload.get("Amount"))
    if not str(payload.get("OrderId") or "").strip() or amount is None:
        return _error("Некорректная сумма или OrderId", "3")
    if payload.get("PayType") not in {None, "T"}:
        return _error("Для терминала доступна двухстадийная оплата", "7")
    try:
        ttl = _parse_positive_int(payload.get("ttl")) or 20
        payment = store.create_payment(payload, ttl)
    except (TypeError, ValueError):
        return _error("OrderId уже используется с другими параметрами", "4")
    response = _payment_response(payment)
    response["PaymentURL"] = f"{settings.public_base_url.rstrip('/')}/pay/{payment['id']}"
    return JSONResponse(response)


@app.post("/v2/GetState")
async def get_state(request: Request) -> JSONResponse:
    payload = await request.json()
    error = _validate_request(payload)
    if error:
        return _error(error, "204")
    payment = store.get_payment(str(payload.get("PaymentId")))
    if payment is None:
        return _error("Платеж не найден", "5")
    payment = store.expire_if_needed(payment)
    return JSONResponse(_payment_response(payment))


@app.post("/v2/Confirm")
async def confirm_payment(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    payload = await request.json()
    error = _validate_request(payload)
    if error:
        return _error(error, "204")
    payment = store.get_payment(str(payload.get("PaymentId")))
    if payment is None:
        return _error("Платеж не найден", "5")
    if payment["status"] == "CONFIRMED":
        return JSONResponse(_payment_response(payment))
    if payment["status"] != "AUTHORIZED":
        return _error("Подтвердить можно только авторизованный платеж", "8")
    amount = _request_amount(payload, payment["authorized_amount"])
    if amount is None or amount > payment["authorized_amount"]:
        return _error("Сумма списания превышает сумму авторизации", "9")
    payment = store.transition(payment["id"], "CONFIRMED", amount)
    _queue_webhook(background_tasks, payment, "CONFIRMED", amount)
    return JSONResponse(_payment_response(payment))


@app.post("/v2/Cancel")
async def cancel_payment(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    payload = await request.json()
    error = _validate_request(payload)
    if error:
        return _error(error, "204")
    payment = store.get_payment(str(payload.get("PaymentId")))
    if payment is None:
        return _error("Платеж не найден", "5")
    if payment["status"] in {"CANCELED", "REFUNDED", "PARTIAL_REFUNDED"}:
        return JSONResponse(_payment_response(payment))
    if payment["status"] == "AUTHORIZED":
        payment = store.transition(payment["id"], "CANCELED", 0)
        _queue_webhook(background_tasks, payment, "CANCELED", 0)
        return JSONResponse(_payment_response(payment))
    if payment["status"] != "CONFIRMED":
        return _error("Платеж нельзя отменить в текущем статусе", "10")
    amount = _request_amount(payload, payment["captured_amount"])
    available = payment["captured_amount"] - payment["refunded_amount"]
    if amount is None or amount > available:
        return _error("Сумма возврата превышает доступную сумму", "11")
    status = "REFUNDED" if amount == available else "PARTIAL_REFUNDED"
    payment = store.transition(payment["id"], status, amount)
    _queue_webhook(background_tasks, payment, status, amount)
    return JSONResponse(_payment_response(payment))


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font:16px system-ui;max-width:440px;margin:40px auto;padding:0 18px;"
        "background:#f5f6f8;color:#1f2937}main{background:white;padding:24px;border-radius:8px;"
        "box-shadow:0 2px 12px #0001}label{display:block;margin:14px 0 6px}input,button{"
        "box-sizing:border-box;width:100%;padding:11px;border:1px solid #cbd5e1;border-radius:5px;"
        "font:inherit}button{margin-top:20px;background:#111827;color:white;cursor:pointer}"
        ".muted{color:#64748b}.error{color:#b91c1c}</style></head><body><main>"
        f"{body}</main></body></html>",
    )


@app.get("/pay/{payment_id}")
async def payment_page(payment_id: str) -> HTMLResponse:
    payment = store.get_payment_by_token(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = store.expire_if_needed(payment)
    if payment["status"] != "NEW":
        return _page(
            "Платеж",
            f"<h1>Платеж {html.escape(payment['status'])}</h1>"
            "<p class='muted'>Эта платежная попытка больше не принимает карту.</p>",
        )
    return _page(
        "Оплата",
        f"<h1>Оплата</h1><p>{html.escape(payment['description'])}</p>"
        f"<p><strong>{payment['amount'] / 100:.2f} ₽</strong></p>"
        f"<form method='post' action='/pay/{quote(payment_id)}/submit'>"
        "<label>Номер карты</label><input name='pan' inputmode='numeric' pattern='[0-9 ]{16,19}' required>"
        "<label>Срок действия</label><input name='exp_date' placeholder='12/30' pattern='[0-9]{2}/[0-9]{2,4}' required>"
        "<label>CVV</label><input name='cvv' inputmode='numeric' pattern='[0-9]{3,4}' maxlength='4' required>"
        "<label>Имя держателя</label><input name='cardholder' minlength='2' required>"
        "<button type='submit'>Оплатить</button></form>",
    )


@app.post("/pay/{payment_id}/submit")
async def submit_card(
    payment_id: str,
    background_tasks: BackgroundTasks,
    pan: str = Form(...),
    exp_date: str = Form(...),
    cvv: str = Form(...),
    cardholder: str = Form(...),
) -> HTMLResponse:
    payment = store.get_payment_by_token(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = store.expire_if_needed(payment)
    if payment["status"] != "NEW":
        return _page("Платеж", "<h1>Платеж недоступен</h1>")
    if not _valid_card_input(pan, exp_date, cvv, cardholder):
        return _page(
            "Ошибка оплаты",
            "<h1>Проверьте данные карты</h1><p class='error'>Нужны корректные PAN, срок, CVV и имя держателя.</p>",
        )
    scenario = get_scenario(pan)
    if scenario is None:
        payment = store.transition(payment["id"], "REJECTED", 0, "3", "Карта не поддерживается")
        _queue_webhook(background_tasks, payment, "REJECTED", 0)
        return _failure_response(
            payment,
            "Ошибка оплаты",
            "<h1>Оплата не прошла</h1><p class='error'>Карта не поддерживается в локальном сценарии.</p>",
        )
    masked_pan = "*" * 8 + "".join(character for character in pan if character.isdigit())[-4:]
    store.set_card_details(payment["id"], masked_pan, scenario.name)
    if scenario.challenge:
        return _page(
            "3DS проверка",
            f"<h1>Подтверждение 3DS</h1><p>Введите OTP-код для карты {html.escape(masked_pan)}.</p>"
            f"<form method='post' action='/pay/{quote(payment_id)}/challenge'>"
            "<label>OTP-код</label><input name='otp' required autofocus>"
            "<button type='submit'>Подтвердить</button></form>",
        )
    return await _finish_card(payment, scenario, background_tasks)


@app.post("/pay/{payment_id}/challenge")
async def finish_challenge(
    payment_id: str,
    background_tasks: BackgroundTasks,
    otp: str = Form(...),
) -> HTMLResponse:
    payment = store.get_payment_by_token(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if otp != "1qwezxc":
        payment = store.transition(payment["id"], "REJECTED", 0, "2015", "Проверка 3DS не пройдена")
        _queue_webhook(background_tasks, payment, "REJECTED", 0)
        return _failure_response(
            payment,
            "Ошибка 3DS",
            "<h1>Оплата не прошла</h1><p class='error'>Неверный OTP-код.</p>",
        )
    scenario = get_scenario(payment["card_mask"] or "") or CardScenario(
        "challenge_success", "AUTHORIZED", "0", "", True
    )
    return await _finish_card(payment, scenario, background_tasks)


async def _finish_card(
    payment: Any,
    scenario: CardScenario,
    background_tasks: BackgroundTasks,
) -> HTMLResponse:
    if scenario.status == "REJECTED":
        payment = store.transition(payment["id"], "REJECTED", 0, scenario.error_code, scenario.message)
        _queue_webhook(background_tasks, payment, "REJECTED", 0)
        return _failure_response(
            payment,
            "Ошибка оплаты",
            f"<h1>Оплата не прошла</h1><p class='error'>{html.escape(scenario.message)}</p>",
        )
    payment = store.transition(payment["id"], "AUTHORIZED", payment["amount"])
    _queue_webhook(background_tasks, payment, "AUTHORIZED", payment["amount"])
    if payment["success_url"]:
        return RedirectResponse(payment["success_url"], status_code=303)
    return _page("Платеж авторизован", "<h1>Оплата авторизована</h1><p>Средства удержаны до подтверждения сделки.</p>")
