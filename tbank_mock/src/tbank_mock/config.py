from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    terminal_key: str
    password: str
    database_path: str
    public_base_url: str
    host: str
    port: int
    webhook_timeout_seconds: float
    webhook_retry_count: int
    webhook_retry_delay_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            terminal_key=os.getenv("TBANK_MOCK_TERMINAL_KEY", "mock-terminal"),
            password=os.getenv("TBANK_MOCK_PASSWORD", "mock-password"),
            database_path=os.getenv("TBANK_MOCK_DATABASE_PATH", "./tbank-mock.db"),
            public_base_url=os.getenv("TBANK_MOCK_PUBLIC_BASE_URL", "http://localhost:18080"),
            host=os.getenv("TBANK_MOCK_HOST", "0.0.0.0"),
            port=int(os.getenv("TBANK_MOCK_PORT", "8080")),
            webhook_timeout_seconds=float(
                os.getenv("TBANK_MOCK_WEBHOOK_TIMEOUT_SECONDS", "3")
            ),
            webhook_retry_count=int(os.getenv("TBANK_MOCK_WEBHOOK_RETRY_COUNT", "5")),
            webhook_retry_delay_seconds=float(
                os.getenv("TBANK_MOCK_WEBHOOK_RETRY_DELAY_SECONDS", "1")
            ),
        )
