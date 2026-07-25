from __future__ import annotations

import json
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


class MockExternalHandler(BaseHTTPRequestHandler):
    requests: deque[dict[str, object]] = deque(maxlen=500)
    requests_lock = Lock()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._respond({"status": "ok"})
            return
        if self.path == "/__mock__/requests":
            with self.requests_lock:
                requests = list(self.requests)
            self._respond({"requests": requests})
            return
        self._respond({"Success": True, "Status": "AUTHORIZED"})

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        try:
            request_payload = json.loads(body)
        except json.JSONDecodeError:
            request_payload = {}
        with self.requests_lock:
            self.requests.append(
                {
                    "method": "POST",
                    "path": self.path,
                    "headers": {
                        "content-type": self.headers.get("Content-Type"),
                    },
                    "body": body.decode("utf-8", errors="replace"),
                },
            )
        if self.path == "/GetState":
            self._respond(
                {
                    "Success": True,
                    "PaymentId": request_payload.get("PaymentId", "unknown"),
                    "Status": "REJECTED",
                    "Amount": 0,
                    "Date": "2026-01-01T10:00:00Z",
                },
            )
            return
        if self.path == "/suggestions/api/4_1/rs/suggest/address":
            self._respond(
                {
                    "suggestions": [
                        {
                            "value": "г. Москва, ул. Тестовая, д. 1",
                            "unrestricted_value": "г. Москва, ул. Тестовая, д. 1",
                            "data": {
                                "fias_id": "test-fias-id",
                                "geo_lat": "55.751244",
                                "geo_lon": "37.618423",
                                "qc_geo": "0",
                            },
                        },
                    ],
                },
            )
            return
        order_id = request_payload.get("OrderId")
        payment_id = f"test-payment-{order_id}" if order_id else "test-payment"
        self._respond(
            {
                "Success": True,
                "PaymentId": payment_id,
                "PaymentURL": f"https://pay.test/confirmation/{payment_id}",
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _respond(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    # The service must be reachable from the Compose network.
    ThreadingHTTPServer(("0.0.0.0", 8080), MockExternalHandler).serve_forever()  # noqa: S104
