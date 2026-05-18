import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.common.exceptions.base import ApplicationError
from app.modules.auth.infrastructure.bcrypt_password_hasher import SecureOtpCodeProvider


class SmtpEmailOtpCodeProvider(SecureOtpCodeProvider):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender_email: str,
        sender_name: str,
        use_tls: bool,
        use_ssl: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender_email = sender_email
        self._sender_name = sender_name
        self._use_tls = use_tls
        self._use_ssl = use_ssl

    async def send_otp_code(self, *, email: str, code: str, expires_in_seconds: int) -> None:
        try:
            await asyncio.to_thread(
                self._send_otp_code_sync,
                email=email,
                code=code,
                expires_in_seconds=expires_in_seconds,
            )
        except (OSError, smtplib.SMTPException) as exc:
            raise ApplicationError("OTP_DELIVERY_FAILED") from exc

    def _send_otp_code_sync(self, *, email: str, code: str, expires_in_seconds: int) -> None:
        message = EmailMessage()
        message["Subject"] = "Your login code"
        message["From"] = formataddr((self._sender_name, self._sender_email))
        message["To"] = email
        message.set_content(_otp_text_body(code, expires_in_seconds))

        if self._use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self._host, self._port, context=context, timeout=10) as smtp:
                smtp.login(self._username, self._password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._use_tls:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._username, self._password)
            smtp.send_message(message)


def _otp_text_body(code: str, expires_in_seconds: int) -> str:
    minutes = max(1, expires_in_seconds // 60)
    return (
        f"Your login code is {code}.\n\n"
        f"This code expires in {minutes} minute(s).\n"
        "If you did not request this code, ignore this email."
    )
