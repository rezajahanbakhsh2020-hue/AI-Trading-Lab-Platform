"""Alert application service.

Derives user-facing market alerts honestly from a real monitored snapshot
or multi-condition alert rules. Alerts are never fabricated: every id and
message detail is built only from real observed inputs.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
import math
import numbers
import time

from src.platform.domain.alert import (
    AlertRule,
    MarketAlert,
    VALID_ALERT_KINDS,
    VALID_ALERT_SEVERITIES,
)
from src.platform.domain.user_authorization import UserAuthorization
from src.platform.services.provider_monitoring import ProviderMonitor, DataFreshnessSnapshot
from src.platform.services.security import SecretSanitizer, SecurityBoundaryService


def _none_if_blank(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _format_age(age: Any) -> Optional[str]:
    if age is None:
        return None
    if isinstance(age, bool) or not isinstance(age, numbers.Real):
        return None
    if not math.isfinite(float(age)):
        return None
    return f"{float(age):.1f}s"


@dataclass(frozen=True)
class AlertEvaluation:
    """Result of evaluating one monitored context for alerts."""

    alert: Optional[MarketAlert] = None
    snapshot: Optional[DataFreshnessSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert": None if self.alert is None else self.alert.to_dict(),
            "snapshot": None if self.snapshot is None else self.snapshot.to_dict(),
        }


class AlertService:
    """Derive user-facing alerts honestly from real monitored snapshots and rule configurations."""

    def __init__(
        self,
        monitor: Optional[ProviderMonitor] = None,
        created_at: Optional[Union[int, float, str]] = None,
        clock: Optional[Callable[[], float]] = None,
        security_service: Optional[SecurityBoundaryService] = None,
        delivery_port: Optional[Any] = None,
    ) -> None:
        if monitor is not None and not isinstance(monitor, ProviderMonitor):
            raise ValueError("monitor must be a ProviderMonitor")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable when provided")
        self._monitor = monitor
        self._created_at = created_at
        self._clock = clock if clock is not None else time.time
        self._security_service = security_service or SecurityBoundaryService()
        self._delivery_port = delivery_port

    def deliver_alert(
        self,
        alert: MarketAlert,
        user_id: str,
        channel: Optional[str] = None,
    ) -> Optional[Any]:
        """Dispatch a generated MarketAlert to target user via configured delivery_port."""
        if not isinstance(alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string")
        if self._delivery_port is None:
            return None

        if hasattr(self._delivery_port, "deliver_alert_to_user"):
            return self._delivery_port.deliver_alert_to_user(
                target_user_id=user_id.strip(),
                alert=alert,
                channel=channel,
            )
        elif hasattr(self._delivery_port, "deliver_alert"):
            return self._delivery_port.deliver_alert(
                user_id=user_id.strip(),
                alert=alert,
                channel=channel,
            )
        return None

    def evaluate(
        self,
        symbol: str,
        timeframe: str,
        market_data_provider_id: str,
        candles_limit: int = 100,
        quote_provider_id: Optional[str] = None,
        max_age_seconds: float = 60.0,
        reference: Optional[Union[int, float, str]] = None,
        include_healthy: bool = False,
    ) -> Optional[MarketAlert]:
        """Evaluate one monitored context and return a single freshness alert (or None)."""
        if self._monitor is None:
            raise ValueError("ProviderMonitor instance required for freshness evaluation")
        if isinstance(include_healthy, bool) is False:
            raise ValueError("include_healthy must be a bool")

        snapshot = self._monitor.monitor(
            symbol=symbol,
            timeframe=timeframe,
            market_data_provider_id=market_data_provider_id,
            candles_limit=candles_limit,
            quote_provider_id=quote_provider_id,
            max_age_seconds=max_age_seconds,
            reference=reference,
        )

        if snapshot.freshness is None:
            return None

        status = snapshot.freshness.status
        if status == "fresh" and not include_healthy:
            return None

        created_at = self._created_at if self._created_at is not None else self._clock()
        alert = self._build_alert(snapshot, status, created_at)
        return alert

    def evaluate_rule(
        self,
        rule: AlertRule,
        current_price: Optional[float] = None,
        signal_action: Optional[str] = None,
        confidence: Optional[float] = None,
        provider_connected: bool = True,
        user: Optional[UserAuthorization] = None,
    ) -> Optional[MarketAlert]:
        """Evaluate a custom user alert rule against observed market/signal state."""
        if not isinstance(rule, AlertRule):
            raise ValueError("rule must be an AlertRule instance")

        if not rule.enabled:
            return None

        created_at = self._created_at if self._created_at is not None else self._clock()
        cond = rule.condition_type

        triggered = False
        severity = "info"
        message = ""
        details: Dict[str, Any] = {
            "rule_id": rule.rule_id,
            "condition_type": cond,
            "kind": rule.kind,
        }

        if cond == "price_above" and rule.threshold is not None and current_price is not None:
            if current_price >= rule.threshold:
                triggered = True
                severity = "warning"
                message = f"Price alert for {rule.symbol}: Price {current_price:.2f} reached or exceeded threshold {rule.threshold:.2f}"
                details["observed_price"] = current_price
                details["threshold"] = rule.threshold

        elif cond == "price_below" and rule.threshold is not None and current_price is not None:
            if current_price <= rule.threshold:
                triggered = True
                severity = "warning"
                message = f"Price alert for {rule.symbol}: Price {current_price:.2f} dropped to or below threshold {rule.threshold:.2f}"
                details["observed_price"] = current_price
                details["threshold"] = rule.threshold

        elif cond == "signal_action" and rule.expected_value and signal_action:
            if signal_action.strip().upper() == rule.expected_value.strip().upper():
                triggered = True
                severity = "info" if signal_action.strip().upper() == "BUY" else "warning"
                message = f"Signal alert for {rule.symbol}: New {signal_action.upper()} signal emitted"
                details["signal_action"] = signal_action
                details["expected_action"] = rule.expected_value

        elif cond == "confidence_below" and rule.threshold is not None and confidence is not None:
            if confidence < rule.threshold:
                triggered = True
                severity = "warning"
                message = f"Signal confidence alert for {rule.symbol}: Confidence {confidence:.2f} is below threshold {rule.threshold:.2f}"
                details["confidence"] = confidence
                details["threshold"] = rule.threshold

        elif cond == "provider_disconnect" and not provider_connected:
            triggered = True
            severity = "critical"
            message = f"Provider alert for {rule.symbol}: Market data provider is disconnected"
            details["provider_connected"] = False

        if not triggered:
            return None

        sanitized_details = SecretSanitizer.sanitize_data(details)
        if not isinstance(sanitized_details, dict):
            sanitized_details = {}

        alert_id = f"{rule.kind}-{rule.rule_id}-{rule.symbol.lower()}"
        alert = MarketAlert(
            id=alert_id,
            kind=rule.kind,
            severity=severity,
            status="active",
            message=message,
            symbol=rule.symbol,
            timeframe=rule.timeframe,
            created_at=created_at,
            details=sanitized_details,
        )

        return alert

    def acknowledge_alert(
        self,
        alert: MarketAlert,
        user: Optional[UserAuthorization] = None,
    ) -> MarketAlert:
        """Acknowledge an active alert."""
        if not isinstance(alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")

        return MarketAlert(
            id=alert.id,
            kind=alert.kind,
            severity=alert.severity,
            status="acknowledged",
            message=alert.message,
            symbol=alert.symbol,
            timeframe=alert.timeframe,
            created_at=alert.created_at,
            details=alert.details,
        )

    def resolve_alert(
        self,
        alert: MarketAlert,
        user: Optional[UserAuthorization] = None,
    ) -> MarketAlert:
        """Resolve an active or acknowledged alert."""
        if not isinstance(alert, MarketAlert):
            raise ValueError("alert must be a MarketAlert instance")

        return MarketAlert(
            id=alert.id,
            kind=alert.kind,
            severity=alert.severity,
            status="resolved",
            message=alert.message,
            symbol=alert.symbol,
            timeframe=alert.timeframe,
            created_at=alert.created_at,
            details=alert.details,
        )

    def _build_alert(
        self,
        snapshot: DataFreshnessSnapshot,
        status: str,
        created_at: Union[int, float, str],
    ) -> MarketAlert:
        severity, alert_id, subject = self._classify(status)
        details: Dict[str, Any] = {}
        details["market_data_provider_id"] = snapshot.market_data_provider_id
        if snapshot.quote_provider_id is not None:
            details["quote_provider_id"] = snapshot.quote_provider_id
        details["candle_count"] = snapshot.candle_count
        if snapshot.quote_status is not None:
            details["quote_status"] = snapshot.quote_status
        details["freshness"] = snapshot.freshness.to_dict()

        sanitized_details = SecretSanitizer.sanitize_data(details)
        if not isinstance(sanitized_details, dict):
            sanitized_details = {}

        message = self._build_message(snapshot, status, subject)
        return MarketAlert(
            id=alert_id,
            kind="freshness",
            severity=severity,
            status="active",
            message=message,
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            created_at=created_at,
            details=sanitized_details,
        )

    def _classify(self, status: str):
        if status == "stale":
            return "warning", "freshness-stale", "Market data is stale"
        if status == "unavailable":
            return "critical", "freshness-unavailable", "Market data is unavailable"
        if status == "unknown":
            return "info", "freshness-unknown", "Market data freshness is unknown"
        return "info", "freshness-ok", "Market data is fresh"

    def _build_message(
        self,
        snapshot: DataFreshnessSnapshot,
        status: str,
        subject: str,
    ) -> str:
        freshness = snapshot.freshness
        parts = [subject, f"{snapshot.symbol}/{snapshot.timeframe}"]
        parts.append(f"from {snapshot.market_data_provider_id}")
        reason = _none_if_blank(freshness.reason)
        if reason is not None:
            parts.append(f"reason: {reason}")
        age = _format_age(freshness.candle_age_seconds)
        if age is None:
            age = _format_age(freshness.quote_age_seconds)
        if age is not None:
            parts.append(f"observed age {age}")
        return ", ".join(parts)
