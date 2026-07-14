import logging

from customer_bot.infrastructure.logger import SafeExtraFormatter


def test_safe_extra_formatter_appends_allowlisted_fields() -> None:
    formatter = SafeExtraFormatter("%(levelname)s %(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=None,
    )
    record.telegram_id = 123
    record.service_key = "secret"

    result = formatter.format(record)

    assert result == "WARNING failed | telegram_id=123"
    assert "secret" not in result
