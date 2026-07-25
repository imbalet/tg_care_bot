import html
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


async def _deliver_webhook(payment: Any, status: str, amount: int) -> None:
    url = payment["notification_url"]
    if not url:
        return
    payload = _webhook_payload(payment, status, amount)
    for attempt in range(settings.webhook_retry_count):
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                response = await client.post(url, json=payload)
            if 200 <= response.status_code < 300:
                return
        except httpx.HTTPError:
            pass
        if attempt + 1 < settings.webhook_retry_count:
            import asyncio

            await asyncio.sleep(settings.webhook_retry_delay_seconds)


def _queue_webhook(background_tasks: BackgroundTasks, payment: Any, status: str, amount: int) -> None:
    background_tasks.add_task(_deliver_webhook, payment, status, amount)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v2/Init")
async def init_payment(request: Request) -> JSONResponse:
    payload = await request.json()
    error = _validate_request(payload)
    if error:
        return _error(error, "204")
    if not payload.get("OrderId") or int(payload.get("Amount", 0)) <= 0:
        return _error("Некорректная сумма или OrderId", "3")
    if payload.get("PayType") not in {None, "T"}:
        return _error("Для терминала доступна двухстадийная оплата", "7")
    try:
        payment = store.create_payment(payload, int(payload.get("ttl") or 20))
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
    amount = int(payload.get("Amount") or payment["authorized_amount"])
    if amount <= 0 or amount > payment["authorized_amount"]:
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
    if payment["status"] == "CANCELED" or payment["status"] == "REFUNDED":
        return JSONResponse(_payment_response(payment))
    if payment["status"] == "AUTHORIZED":
        payment = store.transition(payment["id"], "CANCELED", 0)
        _queue_webhook(background_tasks, payment, "CANCELED", 0)
        return JSONResponse(_payment_response(payment))
    if payment["status"] != "CONFIRMED":
        return _error("Платеж нельзя отменить в текущем статусе", "10")
    amount = int(payload.get("Amount") or payment["captured_amount"])
    available = payment["captured_amount"] - payment["refunded_amount"]
    if amount <= 0 or amount > available:
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
        "<label>Номер карты</label><input name='pan' inputmode='numeric' required>"
        "<label>Срок действия</label><input name='exp_date' placeholder='12/30' required>"
        "<label>CVV</label><input name='cvv' inputmode='numeric' maxlength='4' required>"
        "<label>Имя держателя</label><input name='cardholder' required>"
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
    del exp_date, cvv, cardholder
    payment = store.get_payment_by_token(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = store.expire_if_needed(payment)
    if payment["status"] != "NEW":
        return _page("Платеж", "<h1>Платеж недоступен</h1>")
    scenario = get_scenario(pan)
    if scenario is None:
        return _page("Ошибка оплаты", "<h1>Оплата не прошла</h1><p class='error'>Неверный номер карты.</p>")
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
        return _page("Ошибка 3DS", "<h1>Оплата не прошла</h1><p class='error'>Неверный OTP-код.</p>")
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
        return _page("Ошибка оплаты", f"<h1>Оплата не прошла</h1><p class='error'>{html.escape(scenario.message)}</p>")
    payment = store.transition(payment["id"], "AUTHORIZED", payment["amount"])
    _queue_webhook(background_tasks, payment, "AUTHORIZED", payment["amount"])
    if payment["success_url"]:
        return RedirectResponse(payment["success_url"], status_code=303)
    return _page("Платеж авторизован", "<h1>Оплата авторизована</h1><p>Средства удержаны до подтверждения сделки.</p>")
