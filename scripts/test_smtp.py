"""Test SMTP sending using app utils and current .env settings."""
from app.core.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, ADMIN_EMAIL
from app.utils.email import send_email

print("SMTP_HOST:", SMTP_HOST)
print("SMTP_USER:", SMTP_USER)
print("SMTP_FROM:", SMTP_FROM)

try:
    send_email(ADMIN_EMAIL, "BioSecureGate SMTP test", "This is a test email from your local BioSecureGate instance.")
    print("send_email returned without exception — check inbox/spam.")
except Exception as e:
    print("send_email raised:", repr(e))
