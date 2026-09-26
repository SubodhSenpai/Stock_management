"""Outgoing email over SMTP (Python standard library, no third-party email service).

With no SMTP host configured (the default in development) the message is written to the
log instead, so the OTP flow can be demonstrated without a mail server.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings

# Tie into the existing logger that Uvicorn uses
logger = logging.getLogger("uvicorn.error")

SMTP_TIMEOUT_SECONDS = 10


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        """Send an email, or log it when SMTP is not configured.

        Never raises: a mail failure must not roll back the database work that triggered it.
        """
        if not self.settings.smtp_host:
            print("\n" + "=" * 60, flush=True)
            print(f"📧 [DEV EMAIL / PASSWORD RESET OTP]", flush=True)
            print(f"To: {to}", flush=True)
            print(f"Subject: {subject}", flush=True)
            print("-" * 60, flush=True)
            print(body, flush=True)
            print("=" * 60 + "\n", flush=True)
            logger.info("Email not sent (no SMTP configured). To=%s | %s\n%s", to, subject, body)
            return

        message = EmailMessage()
        message["From"] = self.settings.email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(
                self.settings.smtp_host, self.settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
            ) as smtp:
                smtp.starttls()
                if self.settings.smtp_user:
                    smtp.login(self.settings.smtp_user, self.settings.smtp_password or "")
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError):
            logger.exception("Failed to send email to %s", to)

    def send_password_reset_otp(self, to: str, otp: str, valid_minutes: int) -> None:
        logger.info("🔑 [OTP] Verification code for %s is: %s", to, otp)
        body = (
            "Someone asked to reset your StockSense password.\n\n"
            f"Your verification code is: {otp}\n\n"
            f"The code expires in {valid_minutes} minutes and can be used once.\n"
            "If this was not you, you can ignore this email; your password stays unchanged."
        )
        self.send(to, "Your StockSense password reset code", body)
