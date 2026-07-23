from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class MockExternalHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self._respond({"Success": True, "Status": "AUTHORIZED"})

    def do_POST(self) -> None:  # noqa: N802
        self._respond({"Success": True, "PaymentId": "test-payment"})

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
