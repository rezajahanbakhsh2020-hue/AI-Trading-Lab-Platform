"""Telegram delivery application service (Part 19: Telegram Delivery Service).

Orchestrates signal authorization checks and Telegram message delivery
using TelegramDeliveryPort and UserAuthorizationService.
Enforces security boundary permissions for trade setup details.
"""

from typing import Optional

from src.platform.domain.presented_signal import PresentedSignal
from src.platform.domain.security import Permission
from src.platform.integrations.telegram import TelegramDeliveryPort, TelegramDeliveryResult
from src.platform.services.user_authorization import UserAuthorizationService


class TelegramDeliveryService:
    """Application service for delivering signals to authorized Telegram destinations."""

    def __init__(
        self,
        delivery_port: TelegramDeliveryPort,
        user_auth_service: UserAuthorizationService,
    ) -> None:
        if delivery_port is None or not isinstance(delivery_port, TelegramDeliveryPort):
            raise ValueError("delivery_port must be a TelegramDeliveryPort instance")
        if user_auth_service is None or not isinstance(user_auth_service, UserAuthorizationService):
            raise ValueError("user_auth_service must be a UserAuthorizationService instance")

        self._port = delivery_port
        self._user_auth_svc = user_auth_service

    def deliver_signal_to_user(
        self, user_id: str, signal: PresentedSignal
    ) -> TelegramDeliveryResult:
        """Deliver signal to user_id if user is authorized and policy permits."""
        if not isinstance(signal, PresentedSignal):
            raise ValueError("signal must be a PresentedSignal instance")

        authorized, reason = self._user_auth_svc.evaluate_delivery_permission(
            user_id=user_id, symbol=signal.symbol, strategy_name=signal.strategy_name
        )

        user = self._user_auth_svc.get_authorized_user(user_id)
        chat_id = user.telegram_chat_id if user and user.telegram_chat_id else ""

        if not authorized:
            return TelegramDeliveryResult(
                success=False,
                chat_id=chat_id,
                reason=f"Authorization denied: {reason}",
            )

        # Enforce trade setup permission boundary
        delivery_signal = signal
        if user and not user.has_permission(Permission.READ_TRADE_SETUPS):
            delivery_signal = PresentedSignal(
                signal_id=signal.signal_id,
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                timestamp=signal.timestamp,
                entry_price=None,
                stop_loss=None,
                take_profits=(),
                confidence=signal.confidence,
                strategy_name=signal.strategy_name,
                timeframe=signal.timeframe,
                metadata=signal.metadata,
            )

        return self._port.send_signal(chat_id=chat_id, signal=delivery_signal)
