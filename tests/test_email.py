from unittest.mock import MagicMock

import pytest

from modkit.config import Settings
from modkit.email import parse_recipients, send_email


@pytest.fixture
def smtp(monkeypatch):
    server = MagicMock()
    smtp_cls = MagicMock(return_value=server)
    server.__enter__.return_value = server
    monkeypatch.setattr("modkit.email.sender.smtplib.SMTP", smtp_cls)
    return smtp_cls, server


def test_parse_recipients():
    assert parse_recipients(" a@x.com, b@x.com ,") == ["a@x.com", "b@x.com"]
    assert parse_recipients(["a@x.com"]) == ["a@x.com"]


def test_send_email_builds_message(smtp):
    smtp_cls, server = smtp
    settings = Settings(smtp_host="mail", smtp_port=2525, email_from="bot@x.com")

    result = send_email("a@x.com, b@x.com", "Report", "Body text", settings=settings)

    assert result == {"sent_to": ["a@x.com", "b@x.com"], "subject": "Report"}
    smtp_cls.assert_called_once_with("mail", 2525, timeout=30)
    msg = server.send_message.call_args.args[0]
    assert msg["To"] == "a@x.com, b@x.com"
    assert msg["From"] == "bot@x.com"
    assert msg.get_content().strip() == "Body text"
    server.login.assert_not_called()


def test_send_email_logs_in_with_tls(smtp):
    _, server = smtp
    settings = Settings(smtp_user="u", smtp_password="p", smtp_starttls=True)
    send_email("a@x.com", "s", "b", settings=settings)
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("u", "p")


def test_send_email_requires_recipient(smtp):
    with pytest.raises(ValueError):
        send_email(" , ", "s", "b", settings=Settings())
