from datetime import UTC, datetime, timedelta
import sqlite3
from threading import RLock
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


class PaymentStore:
    def __init__(self, database_path: str) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(
            database_path,
            check_same_thread=False,
            timeout=5,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA busy_timeout=5000")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                terminal_key TEXT NOT NULL,
                order_id TEXT NOT NULL UNIQUE,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                pay_type TEXT NOT NULL,
                notification_url TEXT,
                success_url TEXT,
                fail_url TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                card_mask TEXT,
                card_scenario TEXT,
                authorized_amount INTEGER NOT NULL DEFAULT 0,
                captured_amount INTEGER NOT NULL DEFAULT 0,
                refunded_amount INTEGER NOT NULL DEFAULT 0,
                last_error_code TEXT NOT NULL DEFAULT '0',
                last_message TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS payment_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                amount INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(payment_id, status, amount),
                FOREIGN KEY(payment_id) REFERENCES payments(id)
            );
            """
        )
        self._connection.commit()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create_payment(self, payload: dict[str, Any], ttl_minutes: int) -> sqlite3.Row:
        now = utc_now()
        expires_at = now + timedelta(minutes=max(5, min(ttl_minutes, 20)))
        with self._lock:
            existing = self._connection.execute(
                "SELECT * FROM payments WHERE order_id = ?",
                (str(payload["OrderId"]),),
            ).fetchone()
            if existing is not None:
                if (
                    existing["amount"] != int(payload["Amount"])
                    or existing["terminal_key"] != str(payload["TerminalKey"])
                ):
                    raise ValueError("OrderId is already used with different parameters")
                return existing
            cursor = self._connection.execute(
                """
                INSERT INTO payments (
                    terminal_key, order_id, amount, description, status, pay_type,
                    notification_url, success_url, fail_url, expires_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'NEW', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload["TerminalKey"]),
                    str(payload["OrderId"]),
                    int(payload["Amount"]),
                    str(payload.get("Description") or "Оплата заказа"),
                    str(payload.get("PayType") or "T"),
                    payload.get("NotificationURL"),
                    payload.get("SuccessURL"),
                    payload.get("FailURL"),
                    _iso(expires_at),
                    _iso(now),
                    _iso(now),
                ),
            )
            self._connection.commit()
            return self.get_payment(str(cursor.lastrowid))

    def get_payment(self, payment_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(
                "SELECT * FROM payments WHERE id = ?",
                (str(payment_id),),
            ).fetchone()

    def get_payment_by_token(self, token: str) -> sqlite3.Row | None:
        with self._lock:
            return self._connection.execute(
                "SELECT * FROM payments WHERE id = ?",
                (token,),
            ).fetchone()

    def expire_if_needed(self, payment: sqlite3.Row) -> sqlite3.Row:
        if payment["status"] in {"NEW", "AUTHORIZED"} and _parse(payment["expires_at"]) < utc_now():
            return self.transition(payment["id"], "DEADLINE_EXPIRED", 0, "998", "Срок оплаты истек")
        return payment

    def transition(
        self,
        payment_id: int,
        status: str,
        amount: int,
        error_code: str = "0",
        message: str = "",
    ) -> sqlite3.Row:
        with self._lock:
            payment = self.get_payment(str(payment_id))
            if payment is None:
                raise KeyError("Payment not found")
            now = _iso(utc_now())
            authorized_amount = payment["authorized_amount"]
            captured_amount = payment["captured_amount"]
            refunded_amount = payment["refunded_amount"]
            if status == "AUTHORIZED":
                authorized_amount = amount
            elif status == "CONFIRMED":
                captured_amount += amount
            elif status == "REFUNDED" or status == "PARTIAL_REFUNDED":
                refunded_amount += amount
            self._connection.execute(
                """
                UPDATE payments
                SET status = ?, updated_at = ?, authorized_amount = ?,
                    captured_amount = ?, refunded_amount = ?, last_error_code = ?,
                    last_message = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    authorized_amount,
                    captured_amount,
                    refunded_amount,
                    error_code,
                    message,
                    payment_id,
                ),
            )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO payment_events
                    (payment_id, status, amount, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (payment_id, status, amount, now),
            )
            self._connection.commit()
            return self.get_payment(str(payment_id))

    def event_exists(self, payment_id: int, status: str, amount: int) -> bool:
        with self._lock:
            return self._connection.execute(
                """
                SELECT 1 FROM payment_events
                WHERE payment_id = ? AND status = ? AND amount = ?
                """,
                (payment_id, status, amount),
            ).fetchone() is not None

    def set_card_details(self, payment_id: int, card_mask: str, scenario: str) -> None:
        with self._lock:
            self._connection.execute(
                """
                UPDATE payments
                SET card_mask = ?, card_scenario = ?, updated_at = ?
                WHERE id = ?
                """,
                (card_mask, scenario, _iso(utc_now()), payment_id),
            )
            self._connection.commit()
