"""Signal delivery application service.

Delivers a generated Signal to an authorized consumer through SignalDeliveryPort.
Authorization reuses UserAuthorizationService and SecurityBoundaryService. Channel infrastructure stays
behind the port; this service does not generate, fabricate, or execute trades.
"""

from typing import Optional, Tuple

from src.platform.domain.security import Permission
from src.platform.domain.signal import Signal
from src.platform.domain.signal_delivery import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_NOT_DELIVERED,
    SignalDelivery,
)
from src.platform.integrations.signal_delivery import SignalDeliveryPort
from src.platform.services.user_authorization import UserAuthorizationService

REASON_DELIVERED = "signal delivered"
REASON_CONSUMER_NOT_AUTHORIZED = "consumer is not registered or authorized"
REASON_DELIVERY_DISABLED = "signal delivery is disabled for consumer"
REASON_POLICY_DENIED = "consumer policy does not permit this signal"
REASON_CHANNEL_FAILED = "delivery channel failed"


class SignalDeliveryService:
    """Application service for authorized signal delivery."""

    def __init__(
        self,
        delivery_port: SignalDeliveryPort,
        user_auth_service: UserAuthorizationService,
    ) -> None:
        if delivery_port is None or not isinstance(delivery_port, SignalDeliveryPort):
            raise ValueError("delivery_port must be a SignalDeliveryPort instance")
        if user_auth_service is None or not isinstance(
            user_auth_service, UserAuthorizationService
        ):
            raise ValueError("user_auth_service must be a UserAuthorizationService instance")
        self._port = delivery_port
        self._user_auth_svc = user_auth_service

    def deliver(
        self,
        consumer_id: str,
        signal: Signal,
        symbol: str,
    ) -> SignalDelivery:
        """Authorize the consumer, then deliver through the outbound port."""
        if not isinstance(signal, Signal):
            raise ValueError("signal must be a Signal instance")
        if not isinstance(consumer_id, str) or not consumer_id.strip():
            raise ValueError("consumer_id must be a non-empty string")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        consumer_id = consumer_id.strip()
        symbol = symbol.strip()

        authorized, reason = self._evaluate_authorization(
            consumer_id=consumer_id,
            symbol=symbol,
            strategy_name=signal.strategy_name,
        )
        if not authorized:
            return SignalDelivery(
                status=DELIVERY_STATUS_NOT_DELIVERED,
                reason=reason,
                consumer_id=consumer_id,
                symbol=symbol,
                signal=signal,
            )

        attempt = self._port.deliver(
            consumer_id=consumer_id,
            signal=signal,
            symbol=symbol,
        )
        if attempt.success:
            return SignalDelivery(
                status=DELIVERY_STATUS_DELIVERED,
                reason=REASON_DELIVERED,
                consumer_id=consumer_id,
                symbol=symbol,
                signal=signal,
                channel=attempt.channel,
                detail=attempt.detail,
            )
        return SignalDelivery(
            status=DELIVERY_STATUS_NOT_DELIVERED,
            reason=REASON_CHANNEL_FAILED,
            consumer_id=consumer_id,
            symbol=symbol,
            signal=signal,
            channel=attempt.channel,
            detail=attempt.reason,
        )

    def _evaluate_authorization(
        self,
        consumer_id: str,
        symbol: str,
        strategy_name: Optional[str],
    ) -> Tuple[bool, str]:
        user = self._user_auth_svc.get_authorized_user(consumer_id)
        if user is None:
            return False, REASON_CONSUMER_NOT_AUTHORIZED
        if not user.has_permission(Permission.READ_SIGNALS):
            return False, REASON_CONSUMER_NOT_AUTHORIZED
        if not user.delivery_enabled:
            return False, REASON_DELIVERY_DISABLED
        if user.allowed_symbols and symbol.strip().upper() not in user.allowed_symbols:
            return False, REASON_POLICY_DENIED
        if (
            user.allowed_strategies
            and strategy_name
            and strategy_name.strip() not in user.allowed_strategies
        ):
            return False, REASON_POLICY_DENIED
        return True, REASON_DELIVERED
