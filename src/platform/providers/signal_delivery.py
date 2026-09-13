"""In-memory signal delivery adapter.

Records outbound delivery attempts for tests and development. Does not send
messages, call Telegram, or execute trades.
"""

from typing import Any, Dict, List

from src.platform.domain.signal import Signal
from src.platform.integrations.signal_delivery import (
    SignalDeliveryAttempt,
    SignalDeliveryPort,
)


class RecordingSignalDeliveryAdapter(SignalDeliveryPort):
    """Records delivery attempts without contacting an external channel."""

    def __init__(self, available: bool = True, channel: str = "recording") -> None:
        if not isinstance(available, bool):
            raise ValueError("available must be a boolean")
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("channel must be a non-empty string")
        self.available = available
        self.channel = channel.strip()
        self.delivered: List[Dict[str, Any]] = []

    def deliver(
        self,
        consumer_id: str,
        signal: Signal,
        symbol: str,
    ) -> SignalDeliveryAttempt:
        if not isinstance(signal, Signal):
            raise ValueError("signal must be a Signal instance")
        if not self.available:
            return SignalDeliveryAttempt(
                success=False,
                consumer_id=consumer_id,
                reason="delivery channel is unavailable",
                channel=self.channel,
            )
        record = {
            "consumer_id": consumer_id,
            "symbol": symbol,
            "action": signal.action,
            "strategy_name": signal.strategy_name,
            "timestamp": signal.timestamp,
            "confidence": signal.confidence,
        }
        self.delivered.append(record)
        return SignalDeliveryAttempt(
            success=True,
            consumer_id=consumer_id,
            reason="delivered via RecordingSignalDeliveryAdapter",
            channel=self.channel,
            detail=f"recorded delivery {len(self.delivered)}",
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "RecordingSignalDeliveryAdapter",
            "available": self.available,
            "channel": self.channel,
            "delivered_count": len(self.delivered),
        }
