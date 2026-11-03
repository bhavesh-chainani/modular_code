"""Email module. SMTP for now; add SendGrid / Graph API backends here when a client needs one."""

import smtplib
from email.message import EmailMessage

from modkit.config import Settings, get_settings
from modkit.observability import observation


def parse_recipients(to: str | list[str]) -> list[str]:
    """Accept a list or a comma-separated string (what users type on the canvas)."""
    items = to.split(",") if isinstance(to, str) else to
    return [addr.strip() for addr in items if addr.strip()]


def send_email(
    to: str | list[str],
    subject: str,
    body: str,
    *,
    html: bool = False,
    settings: Settings | None = None,
) -> dict:
    s = settings or get_settings()
    recipients = parse_recipients(to)
    with observation(
        "send-email",
        as_type="tool",
        input={"to": recipients, "subject": subject, "body": body, "html": html},
        metadata={"smtp_host": s.smtp_host, "from": s.email_from},
    ) as obs:
        if not recipients:
            raise ValueError("no recipients given")

        msg = EmailMessage()
        msg["From"] = s.email_from
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body, subtype="html" if html else "plain")

        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user and s.smtp_password:
                smtp.login(s.smtp_user, s.smtp_password.get_secret_value())
            smtp.send_message(msg)
        result = {"sent_to": recipients, "subject": subject}
        obs.update(output=result)
    return result
