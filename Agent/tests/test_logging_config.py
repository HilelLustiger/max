import json
import logging

from app.logging_config import JsonFormatter


def _format(record: logging.LogRecord) -> dict:
    return json.loads(JsonFormatter().format(record))


def test_basic_fields_present():
    record = logging.LogRecord("app.api.chat", logging.INFO, "chat.py", 10, "message_received", (), None)
    payload = _format(record)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.api.chat"
    assert payload["message"] == "message_received"
    assert "timestamp" in payload


def test_extra_fields_are_included():
    record = logging.LogRecord("app.api.chat", logging.INFO, "chat.py", 10, "message_received", (), None)
    record.event = "message_received"
    record.request_id = "abc123"
    payload = _format(record)
    assert payload["event"] == "message_received"
    assert payload["request_id"] == "abc123"


def test_exception_info_is_rendered():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "app.db", logging.ERROR, "session.py", 10, "db_transaction_failed", (), sys.exc_info()
        )
    payload = _format(record)
    assert "ValueError: boom" in payload["exc_info"]
