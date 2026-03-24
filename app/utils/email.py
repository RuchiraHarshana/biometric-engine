import smtplib
from email.message import EmailMessage
from typing import Optional
from app.core import config


def send_email(to: str, subject: str, body: str) -> None:
    host = config.SMTP_HOST
    if not host:
        # SMTP not configured; log to console
        print("SMTP not configured — email content:\n", subject, body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg.set_content(body)

    port = config.SMTP_PORT or 587
    user = config.SMTP_USER
    pwd = config.SMTP_PASS

    with smtplib.SMTP(host, port, timeout=10) as s:
        s.starttls()
        if user:
            s.login(user, pwd)
        s.send_message(msg)
