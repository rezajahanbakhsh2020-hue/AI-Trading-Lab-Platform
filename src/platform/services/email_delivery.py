"""Transactional email delivery application service and factory.

Provides transactional email dispatch for account recovery, security alerts,
and system lifecycle notifications.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

from src.platform.config import PlatformConfig
from src.platform.integrations.email_delivery import EmailDeliveryPort, EmailDeliveryResult
from src.platform.providers.email_delivery import (
    DisabledEmailDeliveryAdapter,
    MockEmailDeliveryAdapter,
    SmtpEmailDeliveryAdapter,
)
from src.platform.services.security import SecretSanitizer

logger = logging.getLogger("platform.email_delivery_service")


class EmailDeliveryService:
    """Application service for managing transactional email delivery and routing."""

    def __init__(
        self,
        adapter: Optional[EmailDeliveryPort] = None,
        config: Optional[PlatformConfig] = None,
    ) -> None:
        self.config = config
        self.adapter = adapter or self._create_adapter_from_config(config)

    def _create_adapter_from_config(self, config: Optional[PlatformConfig]) -> EmailDeliveryPort:
        if not config:
            return DisabledEmailDeliveryAdapter("No PlatformConfig provided.")

        provider = config.email_provider.strip().lower()

        if provider in ("none", "disabled", "off"):
            return DisabledEmailDeliveryAdapter("Email provider is set to 'none'.")

        if provider in ("mock", "test", "testing"):
            return MockEmailDeliveryAdapter(
                configured=True,
                should_succeed=True,
                sender_email=config.email_from or "noreply@platform.local",
            )

        if provider == "smtp":
            if not config.email_host or not config.email_from:
                return DisabledEmailDeliveryAdapter("SMTP email_host or email_from is missing in configuration.")
            return SmtpEmailDeliveryAdapter(
                host=config.email_host,
                port=config.email_port,
                username=config.email_username,
                password=config.email_password,
                sender_email=config.email_from,
                use_tls=config.email_use_tls,
            )

        return DisabledEmailDeliveryAdapter(f"Unknown email provider '{provider}'.")

    def send_recovery_email(
        self,
        to_email: str,
        user_id: str,
        recovery_token: str,
        public_base_url: Optional[str] = None,
    ) -> EmailDeliveryResult:
        """Construct and send password recovery email with single-use token."""
        base_url = (public_base_url or (self.config.public_base_url if self.config else "http://localhost:3000")).rstrip("/")
        recovery_link = f"{base_url}/login?recovery_token={recovery_token}&user_id={user_id}"

        subject = "Account Password Recovery Request"
        text_body = (
            f"Hello {user_id},\n\n"
            f"A password recovery request was initiated for your account.\n"
            f"Use the following secure recovery link to reset your password:\n\n"
            f"  {recovery_link}\n\n"
            f"Alternatively, enter this single-use recovery token in the login modal:\n"
            f"  {recovery_token}\n\n"
            f"This recovery request expires in 1 hour. If you did not request this, please ignore this email.\n"
        )
        html_body = (
            f"<div style='font-family: sans-serif; padding: 16px;'>"
            f"<h2>Account Password Recovery</h2>"
            f"<p>Hello <strong>{user_id}</strong>,</p>"
            f"<p>A password recovery request was initiated for your account.</p>"
            f"<p><a href='{recovery_link}' style='display: inline-block; background: #0284c7; color: white; padding: 10px 16px; text-decoration: none; border-radius: 4px;'>Reset Password</a></p>"
            f"<p>Or enter this single-use token: <code>{recovery_token}</code></p>"
            f"<p style='font-size: 0.85em; color: #666;'>This link expires in 1 hour. If you did not request this reset, no action is required.</p>"
            f"</div>"
        )

        return self.adapter.send_email(
            to_email=to_email,
            subject=subject,
            body_text=text_body,
            body_html=html_body,
        )

    def send_security_notification(
        self,
        to_email: str,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> EmailDeliveryResult:
        """Send a security event notification email."""
        sanitized_title = SecretSanitizer.sanitize_string(title)
        sanitized_msg = SecretSanitizer.sanitize_string(message)
        subject = f"[Security Alert] {sanitized_title}"

        text_body = f"Security Notification: {sanitized_title}\n\n{sanitized_msg}\n"
        if details:
            sanitized_meta = SecretSanitizer.sanitize_data(details)
            text_body += f"\nDetails: {sanitized_meta}\n"

        return self.adapter.send_email(
            to_email=to_email,
            subject=subject,
            body_text=text_body,
        )

    def describe(self) -> Dict[str, Any]:
        """Describe email delivery service state."""
        return {
            "name": "EmailDeliveryService",
            "adapter": self.adapter.describe(),
        }
