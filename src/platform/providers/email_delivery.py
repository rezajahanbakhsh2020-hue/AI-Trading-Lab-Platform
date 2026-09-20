"""Transactional email delivery adapters.

Provides concrete adapters for transactional email delivery:
- SmtpEmailDeliveryAdapter: Real transactional SMTP adapter with TLS/SSL, timeout, and authentication handling.
- MockEmailDeliveryAdapter: In-memory adapter recording delivery attempts for testing.
- DisabledEmailDeliveryAdapter: Safe fail-closed adapter returning NOT_CONFIGURED status when credentials are absent.
"""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import re
import smtplib
import time
import uuid
from typing import Any, Dict, List, Optional

from src.platform.integrations.email_delivery import EmailDeliveryPort, EmailDeliveryResult
from src.platform.services.security import SecretSanitizer

logger = logging.getLogger("platform.email_delivery")


class DisabledEmailDeliveryAdapter(EmailDeliveryPort):
    """Fail-closed email adapter returning honest NOT_CONFIGURED status without making external calls."""

    def __init__(self, reason: str = "Email delivery is not configured") -> None:
        self.reason = reason

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> EmailDeliveryResult:
        return EmailDeliveryResult(
            success=False,
            recipient_email=to_email,
            status_code="NOT_CONFIGURED",
            reason=self.reason,
            externally_delivered=False,
            detail="No transactional email provider configured.",
            timestamp=time.time(),
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "DisabledEmailDeliveryAdapter",
            "provider": "none",
            "configured": False,
            "status": "NOT_CONFIGURED",
        }


class MockEmailDeliveryAdapter(EmailDeliveryPort):
    """Mock transactional email adapter for unit testing and CI without external network access."""

    def __init__(
        self,
        configured: bool = True,
        should_succeed: bool = True,
        sender_email: str = "noreply@platform.local",
    ) -> None:
        self.configured = configured
        self.should_succeed = should_succeed
        self.sender_email = sender_email
        self.sent_messages: List[Dict[str, Any]] = []

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> EmailDeliveryResult:
        clean_to = to_email.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_to):
            return EmailDeliveryResult(
                success=False,
                recipient_email=to_email,
                status_code="INVALID_RECIPIENT",
                reason="Recipient email address is invalid.",
                externally_delivered=False,
                timestamp=time.time(),
            )

        if not self.configured:
            return EmailDeliveryResult(
                success=False,
                recipient_email=clean_to,
                status_code="NOT_CONFIGURED",
                reason="Mock email provider marked as not configured.",
                externally_delivered=False,
                timestamp=time.time(),
            )

        if not self.should_succeed:
            return EmailDeliveryResult(
                success=False,
                recipient_email=clean_to,
                status_code="DELIVERY_FAILED",
                reason="Simulated email delivery failure in MockEmailDeliveryAdapter.",
                externally_delivered=False,
                timestamp=time.time(),
            )

        msg_id = f"mock_msg_{uuid.uuid4().hex[:12]}"
        recorded_msg = {
            "message_id": msg_id,
            "to_email": clean_to,
            "from_email": sender_email or self.sender_email,
            "subject": SecretSanitizer.sanitize_string(subject),
            "body_text": SecretSanitizer.sanitize_string(body_text),
            "body_html": SecretSanitizer.sanitize_string(body_html) if body_html else None,
            "timestamp": time.time(),
        }
        self.sent_messages.append(recorded_msg)

        return EmailDeliveryResult(
            success=True,
            recipient_email=clean_to,
            status_code="SENT",
            reason="Email sent via MockEmailDeliveryAdapter.",
            message_id=msg_id,
            externally_delivered=True,
            detail="Mock external delivery recorded successfully.",
            timestamp=time.time(),
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "MockEmailDeliveryAdapter",
            "provider": "mock",
            "configured": self.configured,
            "sent_count": len(self.sent_messages),
        }


class SmtpEmailDeliveryAdapter(EmailDeliveryPort):
    """Production transactional SMTP email delivery adapter with TLS/SSL and timeout handling."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sender_email: Optional[str] = None,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self.host = host.strip() if host else ""
        self.port = port
        self.username = username
        self.password = password
        self.sender_email = sender_email.strip().lower() if sender_email else (username.strip().lower() if username else "noreply@platform.local")
        self.use_tls = use_tls
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Evaluate if required SMTP parameters are present."""
        return bool(self.host and self.sender_email)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> EmailDeliveryResult:
        if not self.is_configured:
            return EmailDeliveryResult(
                success=False,
                recipient_email=to_email,
                status_code="NOT_CONFIGURED",
                reason="SMTP provider credentials or host missing.",
                externally_delivered=False,
                timestamp=time.time(),
            )

        clean_to = to_email.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_to):
            return EmailDeliveryResult(
                success=False,
                recipient_email=to_email,
                status_code="INVALID_RECIPIENT",
                reason="Recipient email address is invalid.",
                externally_delivered=False,
                timestamp=time.time(),
            )

        from_addr = (sender_email or self.sender_email).strip().lower()

        # Build MIME Message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = SecretSanitizer.sanitize_string(subject)
        msg["From"] = from_addr
        msg["To"] = clean_to

        sanitized_text = SecretSanitizer.sanitize_string(body_text)
        part_text = MIMEText(sanitized_text, "plain", "utf-8")
        msg.attach(part_text)

        if body_html:
            sanitized_html = SecretSanitizer.sanitize_string(body_html)
            part_html = MIMEText(sanitized_html, "html", "utf-8")
            msg.attach(part_html)

        msg_id = f"smtp_msg_{uuid.uuid4().hex[:12]}"

        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()

                if self.username and self.password:
                    server.login(self.username, self.password)

                server.sendmail(from_addr, [clean_to], msg.as_string())

            logger.info("Successfully sent transactional email to %s via SMTP host %s", clean_to, self.host)
            return EmailDeliveryResult(
                success=True,
                recipient_email=clean_to,
                status_code="SENT",
                reason=f"Successfully sent via SMTP ({self.host}).",
                message_id=msg_id,
                externally_delivered=True,
                detail=f"Dispatched via SMTP server {self.host}:{self.port}",
                timestamp=time.time(),
            )

        except Exception as err:
            logger.error("Failed to send transactional email to %s via SMTP (%s): %s", clean_to, self.host, str(err))
            return EmailDeliveryResult(
                success=False,
                recipient_email=clean_to,
                status_code="DELIVERY_FAILED",
                reason="SMTP email delivery failed.",
                externally_delivered=False,
                detail=f"SMTP Error: {type(err).__name__}",
                timestamp=time.time(),
            )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "SmtpEmailDeliveryAdapter",
            "provider": "smtp",
            "configured": self.is_configured,
            "host": self.host,
            "port": self.port,
            "use_tls": self.use_tls,
            "sender_email": self.sender_email,
        }
