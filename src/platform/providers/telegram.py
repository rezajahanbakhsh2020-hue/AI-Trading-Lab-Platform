"""Mock Telegram delivery adapter (Part 19: Telegram Provider Adapter).

In-memory provider adapter implementing TelegramDeliveryPort for testing and
development environments where real Telegram bot credentials are not configured.
"""

from typing import Any, Dict, List, Optional

from src.platform.domain.presented_signal import PresentedSignal
from src.platform.integrations.telegram import TelegramDeliveryPort, TelegramDeliveryResult


class MockTelegramAdapter(TelegramDeliveryPort):
    """Mock Telegram adapter for testing signal message formatting and delivery."""

    def __init__(self, is_configured: bool = True) -> None:
        self.is_configured = is_configured
        self.delivered_messages: List[Dict[str, Any]] = []

    def send_signal(
        self,
        chat_id: str,
        signal: PresentedSignal,
        correlation_id: Optional[str] = None,
    ) -> TelegramDeliveryResult:
        corr_id = correlation_id or f"tg_corr_{signal.signal_id}"
        if not self.is_configured:
            return TelegramDeliveryResult(
                success=False,
                chat_id=chat_id,
                reason="Telegram bot credentials not configured in environment",
                failure_code="UNCONFIGURED_CREDENTIALS",
                is_retryable=False,
                correlation_id=corr_id,
            )

        if not chat_id or not isinstance(chat_id, str) or not chat_id.strip():
            return TelegramDeliveryResult(
                success=False,
                chat_id=chat_id or "",
                reason="Invalid or empty chat_id",
                failure_code="INVALID_CHAT_ID",
                is_retryable=False,
                correlation_id=corr_id,
            )

        if not isinstance(signal, PresentedSignal):
            raise ValueError("signal must be a PresentedSignal instance")

        msg_id = f"mock_msg_{len(self.delivered_messages) + 1}"
        formatted_text = format_telegram_signal_message(signal)
        record = {
            "message_id": msg_id,
            "chat_id": chat_id,
            "signal_id": signal.signal_id,
            "text": formatted_text,
            "correlation_id": corr_id,
        }
        self.delivered_messages.append(record)

        return TelegramDeliveryResult(
            success=True,
            chat_id=chat_id,
            message_id=msg_id,
            reason="delivered via MockTelegramAdapter",
            correlation_id=corr_id,
        )

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "MockTelegramAdapter",
            "is_configured": self.is_configured,
            "delivered_count": len(self.delivered_messages),
        }


def format_telegram_signal_message(signal: PresentedSignal) -> str:
    """Format a PresentedSignal into a clean, professional Telegram message string."""
    action_emoji = "🟢" if signal.signal_type == "buy" else "🔴" if signal.signal_type == "sell" else "⚪"
    lines = [
        f"{action_emoji} <b>SIGNAL ALERT: {signal.symbol.upper()} [{signal.signal_type.upper()}]</b>",
        f"Strategy: {signal.strategy_name or 'N/A'}",
        f"Timeframe: {signal.timeframe or 'N/A'}",
    ]

    if signal.entry_price is not None:
        lines.append(f"Entry Price: {signal.entry_price:.2f}")

    if signal.stop_loss is not None:
        lines.append(f"Stop Loss: {signal.stop_loss:.2f}")

    if signal.take_profits:
        for i, tp in enumerate(signal.take_profits, 1):
            lines.append(f"TP{i}: {tp:.2f}")

    if signal.confidence is not None:
        lines.append(f"Confidence: {signal.confidence * 100.0:.1f}%")

    lines.append(f"Signal ID: {signal.signal_id}")
    return "\n".join(lines)
